from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import AppSettings, Device, DeviceDNSActivity
from ..integrations.pihole import PiHoleClient, PiHoleError, sync_pihole


class PiHoleClientTests(SimpleTestCase):
    @patch("core.integrations.pihole.requests.request")
    def test_client_authenticates_with_application_password_and_session_header(self, request):
        auth_response = Mock(status_code=200)
        auth_response.raise_for_status.return_value = None
        auth_response.json.return_value = {
            "session": {"valid": True, "sid": "session-id"}
        }
        version_response = Mock(status_code=200)
        version_response.raise_for_status.return_value = None
        version_response.json.return_value = {"version": {}}
        request.side_effect = [auth_response, version_response]

        client = PiHoleClient("http://pihole.local/admin/", "app-password")
        client.authenticate()
        client.version()

        self.assertEqual(client.base_url, "http://pihole.local")
        self.assertEqual(request.call_args_list[0].args[:2], ("POST", "http://pihole.local/api/auth"))
        self.assertEqual(request.call_args_list[0].kwargs["json"], {"password": "app-password"})
        self.assertEqual(
            request.call_args_list[1].kwargs["headers"]["X-FTL-SID"],
            "session-id",
        )

    def test_client_rejects_non_http_url(self):
        with self.assertRaises(PiHoleError):
            PiHoleClient("pihole.local")


class PiHoleIntegrationTests(TestCase):
    def setUp(self):
        self.device = Device(
            name="Laptop",
            hostname="laptop",
            ip="192.168.1.20",
            mac="aa:bb:cc:dd:ee:20",
        )
        self.device.save(ip_observed_at=timezone.now() - timedelta(days=1))
        self.config = AppSettings.load()
        self.config.pihole_enabled = True
        self.config.pihole_url = "http://pihole.local"
        self.config.pihole_password = "app-password"
        self.config.save()

    def query(self, *, query_id=10, seconds_ago=1, status="FORWARDED"):
        return {
            "id": query_id,
            "time": (timezone.now() - timedelta(seconds=seconds_ago)).timestamp(),
            "type": "A",
            "domain": "Example.COM.",
            "status": status,
            "client": {"ip": self.device.ip, "name": self.device.hostname},
        }

    @patch("core.integrations.pihole.PiHoleClient")
    def test_sync_aggregates_queries_and_does_not_count_cursor_twice(self, client_class):
        entries = [
            self.query(query_id=12, seconds_ago=1),
            self.query(query_id=11, seconds_ago=2, status="GRAVITY"),
        ]
        client = client_class.return_value
        client.dhcp_leases.return_value = {"leases": []}
        client.queries.return_value = {"queries": entries, "cursor": None}

        result = sync_pihole(self.config)

        self.assertEqual(result["matched"], 2)
        activity = DeviceDNSActivity.objects.get(device=self.device, domain="example.com")
        self.assertEqual(activity.query_count, 2)
        self.assertEqual(activity.blocked_count, 1)

        second = sync_pihole(AppSettings.load())
        self.assertEqual(second["processed"], 0)
        activity.refresh_from_db()
        self.assertEqual(activity.query_count, 2)
        self.assertEqual(client.close.call_count, 2)

    @patch("core.integrations.pihole.PiHoleClient")
    def test_dhcp_updates_ip_but_protects_known_device_identity(self, client_class):
        self.device.known = True
        self.device.icon = "desktop"
        self.device.save(update_fields=["known", "icon"])
        client = client_class.return_value
        client.dhcp_leases.return_value = {
            "leases": [
                {
                    "ip": "192.168.1.42",
                    "hwaddr": self.device.mac,
                    "name": "replacement-name",
                }
            ]
        }
        client.queries.return_value = {"queries": [], "cursor": None}

        result = sync_pihole(self.config)

        self.device.refresh_from_db()
        self.assertEqual(result["devices_updated"], 1)
        self.assertEqual(self.device.ip, "192.168.1.42")
        self.assertEqual(self.device.name, "Laptop")
        self.assertEqual(self.device.hostname, "laptop")
        self.assertEqual(self.device.icon, "desktop")

    @patch("core.integrations.pihole.PiHoleClient")
    def test_dhcp_discovers_device_without_marking_existing_devices_offline(self, client_class):
        self.device.online = True
        self.device.save(update_fields=["online"])
        client = client_class.return_value
        client.dhcp_leases.return_value = {
            "leases": [
                {
                    "ip": "192.168.1.33",
                    "hwaddr": "aa:bb:cc:dd:ee:33",
                    "name": "tablet",
                }
            ]
        }
        client.queries.return_value = {"queries": [], "cursor": None}

        result = sync_pihole(self.config)

        discovered = Device.objects.get(mac="aa:bb:cc:dd:ee:33")
        self.assertEqual(result["devices_discovered"], 1)
        self.assertEqual(discovered.hostname, "tablet")
        self.assertEqual(discovered.hostname_source, Device.IdentitySource.PIHOLE)
        self.assertFalse(discovered.online)
        self.device.refresh_from_db()
        self.assertTrue(self.device.online)

    def test_settings_prevent_two_dns_providers_and_hide_password(self):
        admin = User.objects.create_user("admin", password="password", is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)
        self.config.adguard_enabled = True
        self.config.adguard_url = "http://adguard.local"
        self.config.save()

        response = client.put(
            "/api/v1/settings/",
            {
                "pihole_enabled": True,
                "pihole_url": "http://pihole.local",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        get_response = client.get("/api/v1/settings/")
        self.assertNotIn("pihole_password", get_response.data["data"])

    def test_dns_activity_only_returns_the_active_provider(self):
        now = timezone.now()
        DeviceDNSActivity.objects.create(
            provider="adguard",
            device=self.device,
            domain="old-provider.example",
            query_count=5,
            first_seen=now,
            last_seen=now,
        )
        DeviceDNSActivity.objects.create(
            provider="pihole",
            device=self.device,
            domain="pihole.example",
            query_count=2,
            first_seen=now,
            last_seen=now,
        )
        user = User.objects.create_user("viewer", password="password")
        client = APIClient()
        client.force_authenticate(user)

        response = client.get("/api/v1/dns-activity/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["integration"]["provider_name"], "Pi-hole")
        self.assertEqual(
            [item["domain"] for item in response.data["data"]],
            ["pihole.example"],
        )
