from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..integrations.technitium import (
    TechnitiumClient,
    TechnitiumError,
    find_query_log_provider,
    sync_technitium,
)
from ..models import AppSettings, Device, DeviceDNSActivity


QUERY_PROVIDER = {
    "apps": [
        {
            "name": "Query Logs (Sqlite)",
            "dnsApps": [
                {
                    "classPath": "QueryLogs.App",
                    "isQueryLogs": True,
                }
            ],
        }
    ]
}


class TechnitiumClientTests(SimpleTestCase):
    @patch("core.integrations.technitium.requests.get")
    def test_client_uses_bearer_header_without_putting_token_in_url(self, get):
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "ok", "response": {"apps": []}}
        get.return_value = response

        result = TechnitiumClient(
            "https://dns.example:5380/api/",
            "private-token",
        ).apps()

        self.assertEqual(result, {"apps": []})
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "https://dns.example:5380/api/apps/list")
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"],
            "Bearer private-token",
        )
        self.assertNotIn("private-token", get.call_args.args[0])
        self.assertNotIn("private-token", str(get.call_args.kwargs.get("params")))

    def test_query_log_provider_is_discovered_from_capabilities(self):
        provider = find_query_log_provider(QUERY_PROVIDER)

        self.assertEqual(provider["name"], "Query Logs (Sqlite)")
        self.assertEqual(provider["class_path"], "QueryLogs.App")

    def test_query_log_provider_is_required(self):
        with self.assertRaisesMessage(TechnitiumError, "Query Logs app"):
            find_query_log_provider({"apps": []})

    def test_client_rejects_credentials_and_query_in_url(self):
        for value in (
            "https://admin:secret@dns.example:5380",
            "https://dns.example:5380?token=secret",
        ):
            with self.subTest(value=value), self.assertRaises(TechnitiumError):
                TechnitiumClient(value, "token")


class TechnitiumIntegrationTests(TestCase):
    def setUp(self):
        self.device = Device(
            name="Laptop",
            hostname="laptop",
            ip="192.168.1.20",
            mac="aa:bb:cc:dd:ee:20",
        )
        self.device.save(ip_observed_at=timezone.now() - timedelta(days=1))
        self.config = AppSettings.load()
        self.config.technitium_enabled = True
        self.config.technitium_url = "https://dns.example:5380"
        self.config.technitium_api_token = "private-token"
        self.config.save()

    def query(self, row_number, seen_at, *, client=None, response_type="Recursive"):
        return {
            "rowNumber": row_number,
            "timestamp": seen_at.isoformat(),
            "clientIpAddress": client or self.device.ip,
            "responseType": response_type,
            "rcode": "NoError",
            "qname": "Example.COM.",
            "qtype": "A",
        }

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_sync_aggregates_queries_and_does_not_count_cursor_twice(self, client_class):
        now = timezone.now()
        entries = [
            self.query(1, now - timedelta(seconds=2)),
            self.query(2, now - timedelta(seconds=1), response_type="Blocked"),
        ]
        client = client_class.return_value
        client.apps.return_value = QUERY_PROVIDER
        client.query_logs.return_value = {
            "pageNumber": 1,
            "totalPages": 1,
            "totalEntries": 2,
            "entries": entries,
        }

        result = sync_technitium(self.config)

        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["matched"], 2)
        activity = DeviceDNSActivity.objects.get(
            provider="technitium",
            device=self.device,
            domain="example.com",
        )
        self.assertEqual(activity.query_count, 2)
        self.assertEqual(activity.blocked_count, 1)

        second = sync_technitium(AppSettings.load())

        self.assertEqual(second["processed"], 0)
        activity.refresh_from_db()
        self.assertEqual(activity.query_count, 2)

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_sync_reads_all_query_log_pages(self, client_class):
        now = timezone.now()
        client = client_class.return_value
        client.apps.return_value = QUERY_PROVIDER
        client.query_logs.side_effect = [
            {
                "totalPages": 2,
                "entries": [self.query(1, now - timedelta(seconds=2))],
            },
            {
                "totalPages": 2,
                "entries": [self.query(2, now - timedelta(seconds=1))],
            },
        ]

        result = sync_technitium(self.config)

        self.assertEqual(result["processed"], 2)
        self.assertEqual(client.query_logs.call_count, 2)
        self.assertEqual(
            DeviceDNSActivity.objects.get(provider="technitium").query_count,
            2,
        )

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_sync_uses_ip_owner_at_query_time(self, client_class):
        now = timezone.now()
        old_ip = self.device.ip
        self.device.ip = "192.168.1.21"
        self.device.save(
            update_fields=["ip"],
            ip_observed_at=now - timedelta(minutes=30),
        )
        replacement = Device(
            name="Replacement",
            ip=old_ip,
            mac="aa:bb:cc:dd:ee:21",
        )
        replacement.save(ip_observed_at=now - timedelta(minutes=10))
        client = client_class.return_value
        client.apps.return_value = QUERY_PROVIDER
        client.query_logs.return_value = {
            "totalPages": 1,
            "entries": [
                self.query(1, now - timedelta(minutes=45), client=old_ip),
                self.query(2, now - timedelta(minutes=5), client=old_ip),
            ],
        }

        result = sync_technitium(self.config)

        self.assertEqual(result["matched"], 2)
        self.assertTrue(
            DeviceDNSActivity.objects.filter(
                provider="technitium", device=self.device
            ).exists()
        )
        self.assertTrue(
            DeviceDNSActivity.objects.filter(
                provider="technitium", device=replacement
            ).exists()
        )

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_dhcp_updates_known_device_without_changing_identity(self, client_class):
        self.device.known = True
        self.device.icon = "desktop"
        self.device.save(update_fields=["known", "icon"])
        self.config.technitium_dhcp_enabled = True
        self.config.save(update_fields=["technitium_dhcp_enabled"])
        client = client_class.return_value
        client.apps.return_value = QUERY_PROVIDER
        client.dhcp_leases.return_value = {
            "leases": [
                {
                    "type": "Dynamic",
                    "hardwareAddress": self.device.mac,
                    "address": "192.168.1.42",
                    "hostName": "replacement-name",
                    "leaseExpires": (timezone.now() + timedelta(hours=1)).isoformat(),
                }
            ]
        }
        client.query_logs.return_value = {"totalPages": 1, "entries": []}

        result = sync_technitium(self.config)

        self.device.refresh_from_db()
        self.assertEqual(result["devices_updated"], 1)
        self.assertEqual(self.device.ip, "192.168.1.42")
        self.assertEqual(self.device.name, "Laptop")
        self.assertEqual(self.device.hostname, "laptop")
        self.assertEqual(self.device.icon, "desktop")

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_dhcp_device_creation_requires_explicit_opt_in(self, client_class):
        self.config.technitium_dhcp_enabled = True
        self.config.save(update_fields=["technitium_dhcp_enabled"])
        lease = {
            "type": "Reserved",
            "hardwareAddress": "aa:bb:cc:dd:ee:33",
            "address": "192.168.1.33",
            "hostName": "tablet",
        }
        client = client_class.return_value
        client.apps.return_value = QUERY_PROVIDER
        client.dhcp_leases.return_value = {"leases": [lease]}
        client.query_logs.return_value = {"totalPages": 1, "entries": []}

        first = sync_technitium(self.config)

        self.assertEqual(first["devices_skipped"], 1)
        self.assertFalse(Device.objects.filter(mac=lease["hardwareAddress"]).exists())

        config = AppSettings.load()
        config.technitium_dhcp_create_devices = True
        config.save(update_fields=["technitium_dhcp_create_devices"])
        second = sync_technitium(config)

        discovered = Device.objects.get(mac=lease["hardwareAddress"])
        self.assertEqual(second["devices_discovered"], 1)
        self.assertFalse(discovered.known)
        self.assertFalse(discovered.online)
        self.assertEqual(discovered.hostname_source, Device.IdentitySource.TECHNITIUM)

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_dhcp_skips_expired_and_malformed_leases(self, client_class):
        self.config.technitium_dhcp_enabled = True
        self.config.technitium_dhcp_create_devices = True
        self.config.save(
            update_fields=[
                "technitium_dhcp_enabled",
                "technitium_dhcp_create_devices",
            ]
        )
        client = client_class.return_value
        client.apps.return_value = QUERY_PROVIDER
        client.dhcp_leases.return_value = {
            "leases": [
                {
                    "type": "Dynamic",
                    "hardwareAddress": "aa:bb:cc:dd:ee:40",
                    "address": "192.168.1.40",
                    "leaseExpires": (timezone.now() - timedelta(hours=1)).isoformat(),
                },
                {
                    "type": "Reserved",
                    "hardwareAddress": "not-a-mac",
                    "address": "192.168.1.41",
                },
            ]
        }
        client.query_logs.return_value = {"totalPages": 1, "entries": []}

        result = sync_technitium(self.config)

        self.assertEqual(result["expired_leases"], 1)
        self.assertEqual(result["invalid_leases"], 1)
        self.assertFalse(Device.objects.filter(ip="192.168.1.40").exists())
        self.assertFalse(Device.objects.filter(ip="192.168.1.41").exists())

    @patch("core.integrations.technitium.TechnitiumClient")
    def test_success_clears_a_sanitized_transient_error(self, client_class):
        client = client_class.return_value
        client.apps.side_effect = TechnitiumError("private upstream detail")

        with self.assertRaises(TechnitiumError):
            sync_technitium(self.config)

        self.config.refresh_from_db()
        self.assertNotIn("private upstream detail", self.config.technitium_last_error)
        self.assertTrue(self.config.technitium_last_error)

        client.apps.side_effect = None
        client.apps.return_value = QUERY_PROVIDER
        client.query_logs.return_value = {"totalPages": 1, "entries": []}
        sync_technitium(self.config)

        self.config.refresh_from_db()
        self.assertEqual(self.config.technitium_last_error, "")

    def test_settings_hide_token_and_enforce_one_dns_provider(self):
        admin = User.objects.create_user("admin", password="password", is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)

        response = client.get("/api/v1/settings/")

        self.assertNotIn("technitium_api_token", response.data["data"])
        conflict = client.put(
            "/api/v1/settings/",
            {
                "adguard_enabled": True,
                "adguard_url": "http://adguard.local",
                "technitium_enabled": True,
            },
            format="json",
        )
        self.assertEqual(conflict.status_code, 400)

        keep = client.put(
            "/api/v1/settings/",
            {
                "technitium_enabled": True,
                "technitium_url": "https://dns.example:5380/api/",
                "technitium_api_token": "",
            },
            format="json",
        )
        self.assertEqual(keep.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.technitium_api_token, "private-token")
        self.assertEqual(self.config.technitium_url, "https://dns.example:5380")

    def test_settings_require_dhcp_sync_before_lease_device_creation(self):
        admin = User.objects.create_user("dhcp-admin", password="password", is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)

        response = client.put(
            "/api/v1/settings/",
            {
                "technitium_dhcp_enabled": False,
                "technitium_dhcp_create_devices": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("technitium_dhcp_create_devices", response.data)

    @patch("core.views.integrations.test_technitium_connection")
    def test_connection_endpoint_uses_saved_token(self, test_connection):
        test_connection.return_value = {
            "query_log_app": "Query Logs (Sqlite)",
            "active_leases": 0,
        }
        admin = User.objects.create_user("api-admin", password="password", is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)

        response = client.post(
            "/api/v1/integrations/technitium/test/",
            {"url": self.config.technitium_url},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        test_connection.assert_called_once_with(
            self.config.technitium_url,
            "private-token",
            dhcp_enabled=False,
        )
        self.assertNotIn("private-token", str(response.data))

    def test_connection_endpoint_requires_admin(self):
        viewer = User.objects.create_user("api-viewer", password="password")
        client = APIClient()
        client.force_authenticate(viewer)

        response = client.post(
            "/api/v1/integrations/technitium/test/",
            {"url": self.config.technitium_url},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_dns_activity_returns_technitium_as_active_provider(self):
        now = timezone.now()
        DeviceDNSActivity.objects.create(
            provider="technitium",
            device=self.device,
            domain="technitium.example",
            query_count=1,
            first_seen=now,
            last_seen=now,
        )
        viewer = User.objects.create_user("viewer", password="password")
        client = APIClient()
        client.force_authenticate(viewer)

        response = client.get("/api/v1/dns-activity/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["integration"]["provider_name"],
            "Technitium DNS Server",
        )
        self.assertEqual(response.data["data"][0]["domain"], "technitium.example")
