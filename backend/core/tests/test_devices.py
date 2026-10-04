from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import (
    AppSettings,
    Device,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)

class DeviceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(
            name="Laptop",
            ip="192.168.1.20",
            mac="aa:aa:aa:aa:aa:aa",
        )
        self.scan_run = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.SUCCESS,
            devices_seen=1,
            online_devices=1,
        )
        self.event = NetworkEvent.objects.create(
            scan_run=self.scan_run,
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Laptop came online",
        )
        self.delivery = NotificationDelivery.objects.create(
            event=self.event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.FAILED,
            attempts=1,
        )

    def test_device_search_matches_hostname_and_vendor(self):
        self.device.hostname = "office-workstation"
        self.device.vendor = "Example Hardware Ltd."
        self.device.save(update_fields=["hostname", "vendor"])

        hostname_response = self.client.get(
            "/api/v1/device/",
            {"search": "workstation"},
        )
        vendor_response = self.client.get(
            "/api/v1/device/",
            {"search": "hardware"},
        )

        self.assertEqual(hostname_response.status_code, 200)
        self.assertEqual(vendor_response.status_code, 200)
        self.assertEqual(hostname_response.data["data"][0]["id"], self.device.id)
        self.assertEqual(vendor_response.data["data"][0]["id"], self.device.id)

    def test_removing_network_range_marks_only_previously_monitored_devices_offline(self):
        removed_device = Device.objects.create(
            name="Removed VLAN device",
            ip="192.168.1.50",
            mac="aa:bb:cc:dd:ee:50",
            online=True,
            status=Device.Status.ONLINE,
        )
        unrelated_device = Device.objects.create(
            name="Imported external device",
            ip="192.168.30.50",
            mac="aa:bb:cc:dd:ee:60",
            online=True,
            status=Device.Status.ONLINE,
        )

        response = self.client.put(
            "/api/v1/settings/",
            {"scan_ranges": ["192.168.20.0/24"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        removed_device.refresh_from_db()
        unrelated_device.refresh_from_db()
        self.device.refresh_from_db()
        self.assertFalse(removed_device.online)
        self.assertFalse(self.device.online)
        self.assertEqual(removed_device.status, Device.Status.OFFLINE)
        self.assertEqual(removed_device.status_source, Device.StatusSource.NONE)
        self.assertEqual(
            removed_device.status_reason,
            "Outside the configured network ranges.",
        )
        self.assertTrue(unrelated_device.online)
        self.assertFalse(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            ).exists()
        )
        self.assertIn(
            "2 devices were marked offline",
            response.data["notification"]["message"],
        )

    def test_device_endpoint_paginates_devices(self):
        Device.objects.create(
            name="Tablet",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
        )
        Device.objects.create(
            name="Phone",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
        )

        response = self.client.get("/api/v1/device/", {"limit": 2, "offset": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["pagination"]["count"], 3)
        self.assertEqual(response.data["pagination"]["limit"], 2)
        self.assertEqual(response.data["pagination"]["offset"], 0)
        self.assertEqual(response.data["pagination"]["next_offset"], 2)

    def test_device_endpoint_sorts_by_name(self):
        Device.objects.create(
            name="Access point",
            ip="192.168.1.30",
            mac="bb:bb:bb:bb:bb:bb",
        )
        Device.objects.create(
            name="Camera",
            ip="192.168.1.40",
            mac="cc:cc:cc:cc:cc:cc",
        )

        response = self.client.get("/api/v1/device/", {"ordering": "name"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [device["name"] for device in response.data["data"]],
            ["Access point", "Camera", "Laptop"],
        )

    def test_device_endpoint_sorts_by_ip_naturally(self):
        Device.objects.create(
            name="Low IP",
            ip="192.168.1.2",
            mac="bb:bb:bb:bb:bb:bb",
        )
        Device.objects.create(
            name="High IP",
            ip="192.168.1.100",
            mac="cc:cc:cc:cc:cc:cc",
        )

        response = self.client.get("/api/v1/device/", {"ordering": "ip"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [device["ip"] for device in response.data["data"]],
            ["192.168.1.2", "192.168.1.20", "192.168.1.100"],
        )

    def test_device_endpoint_sorts_by_first_seen(self):
        now = timezone.now()
        self.device.firstseen = now - timedelta(days=10)
        self.device.save(update_fields=["firstseen"])
        older = Device.objects.create(
            name="Older device",
            ip="192.168.1.30",
            mac="bb:bb:bb:bb:bb:bb",
            firstseen=now - timedelta(days=30),
        )
        newer = Device.objects.create(
            name="Newer device",
            ip="192.168.1.40",
            mac="cc:cc:cc:cc:cc:cc",
            firstseen=now - timedelta(days=1),
        )

        response = self.client.get(
            "/api/v1/device/",
            {"ordering": "-firstseen"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [device["id"] for device in response.data["data"]],
            [newer.id, self.device.id, older.id],
        )

    def test_device_endpoint_filters_by_first_seen_period(self):
        now = timezone.now()
        self.device.firstseen = now - timedelta(days=20)
        self.device.save(update_fields=["firstseen"])
        recent = Device.objects.create(
            name="Recent device",
            ip="192.168.1.30",
            mac="bb:bb:bb:bb:bb:bb",
            firstseen=now - timedelta(days=2),
        )
        Device.objects.create(
            name="Old device",
            ip="192.168.1.40",
            mac="cc:cc:cc:cc:cc:cc",
            firstseen=now - timedelta(days=40),
        )

        response = self.client.get("/api/v1/device/", {"first_seen": "7d"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["id"], recent.id)

    def test_device_endpoint_filters_today_in_configured_timezone(self):
        config = AppSettings.load()
        config.time_zone = "Asia/Jerusalem"
        config.save(update_fields=["time_zone"])
        self.device.firstseen = datetime(2026, 9, 10, 20, 59)
        self.device.save(update_fields=["firstseen"])
        today = Device.objects.create(
            name="Today device",
            ip="192.168.1.30",
            mac="bb:bb:bb:bb:bb:bb",
            firstseen=datetime(2026, 9, 10, 21, 1),
        )

        with patch(
            "core.views.devices.timezone.now",
            return_value=datetime(2026, 9, 10, 22, 30),
        ):
            response = self.client.get("/api/v1/device/", {"first_seen": "today"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["id"], today.id)

    def test_device_endpoint_filters_by_configured_network_ranges(self):
        config = AppSettings.load()
        config.ip_range = "192.168.1.0/24"
        config.scan_ranges = ["192.168.1.0/24", "192.168.20.0/24"]
        config.save(update_fields=["ip_range", "scan_ranges"])
        vlan_device = Device.objects.create(
            name="VLAN device",
            ip="192.168.20.30",
            mac="bb:bb:bb:bb:bb:bb",
        )
        outside_device = Device.objects.create(
            name="Outside device",
            ip="192.168.30.40",
            mac="cc:cc:cc:cc:cc:cc",
        )

        single_response = self.client.get(
            "/api/v1/device/",
            {"network_ranges": "192.168.20.0/24"},
        )
        multiple_response = self.client.get(
            "/api/v1/device/",
            {"network_ranges": "192.168.1.0/24,192.168.20.0/24"},
        )
        outside_response = self.client.get(
            "/api/v1/device/",
            {"network_ranges": "outside"},
        )

        self.assertEqual(single_response.status_code, 200)
        self.assertEqual(single_response.data["pagination"]["count"], 1)
        self.assertEqual(single_response.data["data"][0]["id"], vlan_device.id)
        self.assertEqual(multiple_response.status_code, 200)
        self.assertEqual(multiple_response.data["pagination"]["count"], 2)
        self.assertEqual(outside_response.status_code, 200)
        self.assertEqual(outside_response.data["pagination"]["count"], 1)
        self.assertEqual(outside_response.data["data"][0]["id"], outside_device.id)

    def test_device_endpoint_rejects_unconfigured_network_range_filter(self):
        response = self.client.get(
            "/api/v1/device/",
            {"network_ranges": "192.168.200.0/24"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("network_ranges", response.data)

    def test_device_endpoint_rejects_invalid_first_seen_period(self):
        response = self.client.get(
            "/api/v1/device/",
            {"first_seen": "yesterday"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("first_seen", response.data)

    def test_device_endpoint_filters_by_display_status(self):
        Device.objects.create(
            name="Status online but stale boolean",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
            online=False,
            status=Device.Status.ONLINE,
        )
        offline_device = Device.objects.create(
            name="Offline camera",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
            online=True,
            status=Device.Status.OFFLINE,
        )

        response = self.client.get("/api/v1/device/", {"status": Device.Status.OFFLINE})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["id"], offline_device.id)
        self.assertEqual(response.data["data"][0]["status"], Device.Status.OFFLINE)

    def test_device_endpoint_rejects_invalid_status_filter(self):
        response = self.client.get("/api/v1/device/", {"status": "gone"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

    def test_device_endpoint_counters_include_current_open_ports(self):
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)
        DevicePort.objects.create(
            device=self.device,
            port=443,
            protocol="tcp",
            open=False,
        )

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["counters"]["open_ports"], 1)

    def test_device_endpoint_separates_visitors_from_primary_counters(self):
        online_visitor = Device.objects.create(
            name="Visiting phone",
            ip="192.168.1.40",
            mac="bb:bb:bb:bb:bb:40",
            known=True,
            is_visitor=True,
            status=Device.Status.ONLINE,
        )
        Device.objects.create(
            name="Away visitor",
            ip="192.168.1.41",
            mac="bb:bb:bb:bb:bb:41",
            known=True,
            is_visitor=True,
            online=False,
            status=Device.Status.OFFLINE,
        )
        Device.objects.create(
            name="Archived device",
            ip="192.168.1.42",
            mac="bb:bb:bb:bb:bb:42",
            archived=True,
        )

        response = self.client.get("/api/v1/device/")
        visitors = self.client.get("/api/v1/device/", {"is_visitor": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["counters"]["all_devices"], 1)
        self.assertEqual(response.data["counters"]["online_devices"], 1)
        self.assertEqual(response.data["counters"]["visitor_devices"], 2)
        self.assertEqual(response.data["counters"]["online_visitors"], 1)
        self.assertEqual(response.data["counters"]["archived_devices"], 1)
        self.assertEqual(visitors.data["pagination"]["count"], 2)
        self.assertEqual(visitors.data["data"][0]["is_visitor"], True)
        self.assertIn(online_visitor.id, [device["id"] for device in visitors.data["data"]])

    def test_device_endpoint_returns_utc_datetime_strings(self):
        self.device.last_status_check = timezone.now()
        self.device.last_port_scan = timezone.now()
        self.device.save(update_fields=["last_status_check", "last_port_scan"])
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertTrue(device["firstseen"].endswith("Z"))
        self.assertTrue(device["lastseen"].endswith("Z"))
        self.assertTrue(device["last_status_check"].endswith("Z"))
        self.assertTrue(device["last_port_scan"].endswith("Z"))
        self.assertTrue(device["open_ports"][0]["firstseen"].endswith("Z"))
        self.assertTrue(device["open_ports"][0]["lastseen"].endswith("Z"))

    def test_device_endpoint_includes_contextual_port_guidance(self):
        self.device.known = True
        self.device.role = "printer"
        self.device.icon = "printer"
        self.device.vendor = "Brother"
        self.device.save(update_fields=["known", "role", "icon", "vendor"])
        DevicePort.objects.create(
            device=self.device,
            port=631,
            protocol="tcp",
            service="ipp",
            open=True,
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]
        guidance = device["open_ports"][0]["guidance"]

        self.assertEqual(guidance["service_name"], "IPP")
        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["identification_basis"], "port_mapping")
        self.assertEqual(guidance["registry_service"], "ipp")
        self.assertIn("local network", guidance["scope_notice"])

    def test_device_endpoint_returns_cautious_guidance_for_ambiguous_port(self):
        self.device.known = True
        self.device.vendor = "Android"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(
            device=self.device,
            port=8443,
            protocol="tcp",
            service="https-alt",
            open=True,
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]
        guidance = device["open_ports"][0]["guidance"]

        self.assertEqual(guidance["recommendation"], "review")
        self.assertIn("does not prove", guidance["context"])
        self.assertIn("does not show", guidance["scope_notice"])

    def test_device_endpoint_labels_port_8080_as_web_api_service(self):
        self.device.known = True
        self.device.vendor = "Matter"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=8080, protocol="tcp", open=True)

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        reason = next(
            reason for reason in device["risk_reasons"]
            if reason.startswith("Risky open ports: tcp/8080 (Web/API service)")
        )
        self.assertIn("check the device documentation", reason)

    def test_device_rejects_follow_ip_for_hostname_link(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {
                "external_url": "https://device.example.test/admin",
                "external_url_follow_device_ip": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("external_url_follow_device_ip", response.data["info"])

    def test_device_endpoint_rejects_too_large_page_size(self):
        response = self.client.get("/api/v1/device/", {"limit": 101})

        self.assertEqual(response.status_code, 400)
        self.assertIn("limit", response.data)
