from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .docker_inventory import (
    DockerInventoryError,
    apply_docker_inventory,
    collect_local_inventory,
    sync_enabled_docker_hosts,
)
from .models import Device, DevicePort, DockerContainer, DockerHost, NetworkEvent


def inventory_payload(*, network_mode="bridge", addresses=None, ports=None):
    return {
        "host": {
            "name": "docker-one",
            "docker_version": "28.0.1",
            "operating_system": "Linux",
            "architecture": "x86_64",
        },
        "containers": [
            {
                "id": "a" * 64,
                "name": "web",
                "image": "nginx:stable",
                "image_id": "sha256:test",
                "state": "running",
                "health": "healthy",
                "status": "Up 2 hours",
                "network_mode": network_mode,
                "addresses": addresses or [],
                "published_ports": ports or [],
                "started_at": "2026-09-28T08:00:00Z",
                "restart_count": 2,
            }
        ],
    }


class DockerCollectorTests(TestCase):
    @patch("core.docker_inventory._docker_get")
    def test_collects_local_engine_inventory(self, docker_get):
        docker_get.side_effect = [
            {
                "Name": "docker-one",
                "ServerVersion": "28.0.1",
                "OperatingSystem": "Linux",
                "Architecture": "x86_64",
            },
            [{"Id": "a" * 64, "Status": "Up 2 hours"}],
            {
                "Name": "/web",
                "Image": "sha256:test",
                "Config": {"Image": "nginx:stable"},
                "State": {"Status": "running", "StartedAt": "2026-09-28T08:00:00Z"},
                "HostConfig": {"NetworkMode": "bridge"},
                "NetworkSettings": {"Networks": {}, "Ports": {}},
                "RestartCount": 0,
            },
        ]

        payload = collect_local_inventory()

        self.assertEqual(payload["host"]["name"], "docker-one")
        self.assertEqual(payload["containers"][0]["name"], "web")

    @patch("core.docker_inventory._docker_get")
    def test_rejects_invalid_docker_inventory(self, docker_get):
        docker_get.side_effect = [{}, {}]
        with self.assertRaises(DockerInventoryError):
            collect_local_inventory()


class DockerInventoryTests(TestCase):
    def setUp(self):
        self.host_device = Device.objects.create(
            name="Docker server",
            ip="192.168.1.10",
            mac="02:00:00:00:00:10",
            known=True,
        )
        self.host = DockerHost.objects.create(
            device=self.host_device,
            name="Server",
        )

    def test_inventory_records_container_and_later_port_changes(self):
        initial = inventory_payload()
        result = apply_docker_inventory(self.host, initial)

        changed = inventory_payload(
            ports=[
                {
                    "container_port": 80,
                    "host_ip": "0.0.0.0",
                    "host_port": 8080,
                    "protocol": "tcp",
                }
            ]
        )
        changed_result = apply_docker_inventory(
            self.host,
            changed,
        )

        container = DockerContainer.objects.get(host=self.host)
        self.assertEqual(container.name, "web")
        self.assertEqual(container.published_ports[0]["host_port"], 8080)
        self.assertEqual(result["new_containers"], 1)
        self.assertEqual(result["new_published_ports"], 0)
        self.assertEqual(changed_result["new_published_ports"], 1)
        self.assertTrue(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.CONTAINER_DISCOVERED
            ).exists()
        )
        self.assertTrue(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.CONTAINER_PORT_EXPOSED
            ).exists()
        )

    def test_macvlan_address_links_to_existing_device(self):
        container_device = Device.objects.create(
            name="Container device",
            ip="192.168.1.50",
            mac="02:00:00:00:00:50",
            known=True,
        )
        apply_docker_inventory(
            self.host,
            inventory_payload(
                network_mode="macvlan",
                addresses=[
                    {
                        "network": "lan",
                        "driver": "macvlan",
                        "ip": "192.168.1.50",
                        "mac": "02:00:00:00:00:50",
                    }
                ],
            ),
        )
        self.assertEqual(DockerContainer.objects.get().linked_device, container_device)

    def test_missing_container_becomes_inactive(self):
        apply_docker_inventory(self.host, inventory_payload())
        empty = inventory_payload()
        empty["containers"] = []
        apply_docker_inventory(self.host, empty)
        self.assertFalse(DockerContainer.objects.get().active)

    @patch("core.docker_inventory.collect_local_inventory")
    def test_requested_sync_runs_before_interval_and_clears_queue(self, collect):
        collect.return_value = inventory_payload()
        apply_docker_inventory(self.host, inventory_payload())
        self.host.sync_requested = True
        self.host.save(update_fields=["sync_requested"])

        results = sync_enabled_docker_hosts()

        self.host.refresh_from_db()
        self.assertEqual(results[0]["status"], "ok")
        self.assertFalse(self.host.sync_requested)


class DockerInventoryApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.device = Device.objects.create(
            name="Docker server",
            ip="192.168.1.10",
            mac="02:00:00:00:01:10",
            known=True,
        )

    def test_local_host_configuration_is_created_and_queued(self):
        response = self.client.post(
            "/api/v1/integrations/docker/hosts/",
            {
                "device": self.device.id,
                "name": "Server",
                "sync_interval": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["data"]["sync_requested"])

    def test_sync_request_is_queued_for_scheduler(self):
        host = DockerHost.objects.create(device=self.device, name="Server")
        host.sync_requested = False
        host.save(update_fields=["sync_requested"])

        response = self.client.post(f"/api/v1/integrations/docker/hosts/{host.id}/sync/")

        self.assertEqual(response.status_code, 200)
        host.refresh_from_db()
        self.assertTrue(host.sync_requested)

    def test_scan_status_reports_configured_docker_inventory(self):
        DockerHost.objects.create(device=self.device, name="Server")

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["integrations"]["docker"],
            {"configured": True},
        )

    def test_device_context_marks_ports_observed_by_languard(self):
        host = DockerHost.objects.create(
            device=self.device,
            name="Server",
        )
        DockerContainer.objects.create(
            host=host,
            container_id="b" * 64,
            name="api",
            published_ports=[
                {
                    "container_port": 80,
                    "host_ip": "0.0.0.0",
                    "host_port": 8080,
                    "protocol": "tcp",
                }
            ],
        )
        DevicePort.objects.create(device=self.device, port=8080, protocol="tcp")

        response = self.client.get(
            "/api/v1/integrations/docker/device/",
            {"device": self.device.id},
        )
        self.assertEqual(response.status_code, 200)
        port = response.data["data"]["containers"][0]["published_ports"][0]
        self.assertTrue(port["observed_by_languard"])
        self.assertNotIn("agent_url", response.data["data"]["host"])

    def test_inventory_overview_lists_active_containers_for_authenticated_users(self):
        host = DockerHost.objects.create(
            device=self.device,
            name="Server",
            docker_version="29.0.0",
        )
        DockerContainer.objects.create(
            host=host,
            container_id="b" * 64,
            name="web",
            published_ports=[
                {
                    "container_port": 80,
                    "host_ip": "0.0.0.0",
                    "host_port": 8080,
                    "protocol": "tcp",
                }
            ],
        )
        DockerContainer.objects.create(
            host=host,
            container_id="c" * 64,
            name="stopped",
            active=False,
        )
        DevicePort.objects.create(device=self.device, port=8080, protocol="tcp")
        viewer = User.objects.create_user(username="viewer", password="password")
        self.client.force_authenticate(viewer)

        response = self.client.get("/api/v1/integrations/docker/inventory/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["total_containers"], 1)
        self.assertEqual(response.data["data"]["hosts"][0]["docker_version"], "29.0.0")
        containers = response.data["data"]["hosts"][0]["containers"]
        self.assertEqual([container["name"] for container in containers], ["web"])
        self.assertTrue(containers[0]["published_ports"][0]["observed_by_languard"])
