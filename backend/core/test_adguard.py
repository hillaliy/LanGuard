from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .adguard import (
    AdGuardClient,
    AdGuardError,
    sync_adguard_query_log,
    test_adguard_connection,
)
from .maintenance import cleanup_all_activity
from .models import AdGuardUnmatchedClient, AppSettings, Device, DeviceDNSActivity


class AdGuardClientTests(SimpleTestCase):
    @patch("core.adguard.requests.get")
    def test_client_uses_control_api_and_basic_auth(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"version": "1.0"}
        get.return_value = response

        result = AdGuardClient(
            "http://adguard.local:3000/",
            "admin",
            "secret",
        ).status()

        self.assertEqual(result, {"version": "1.0"})
        get.assert_called_once_with(
            "http://adguard.local:3000/control/status",
            params=None,
            auth=("admin", "secret"),
            timeout=10,
            headers={"Accept": "application/json"},
        )

    def test_client_rejects_non_http_url(self):
        with self.assertRaises(AdGuardError):
            AdGuardClient("adguard.local:3000")

    @patch("core.adguard.AdGuardClient")
    def test_connection_requires_query_log(self, client_class):
        client_class.return_value.status.return_value = {"running": True}
        client_class.return_value.query_log_config.return_value = {"enabled": False}

        with self.assertRaisesMessage(AdGuardError, "Enable the query log"):
            test_adguard_connection("http://adguard.local:3000")


class AdGuardIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.viewer = User.objects.create_user(
            username="viewer",
            password="password",
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.viewer_client = APIClient()
        self.viewer_client.force_authenticate(self.viewer)
        self.device = Device.objects.create(
            name="Living room TV",
            ip="192.168.1.20",
            mac="aa:bb:cc:dd:ee:20",
        )
        self.config = AppSettings.load()
        self.config.adguard_enabled = True
        self.config.adguard_url = "http://adguard.local:3000"
        self.config.adguard_username = "admin"
        self.config.adguard_password = "secret"
        self.config.adguard_retention_days = 90
        self.config.save()

    def query(self, *, seconds_ago, domain, query_type="A", reason="NotFilteredNotFound", client=None):
        return {
            "time": (timezone.now() - timedelta(seconds=seconds_ago)).isoformat(),
            "client": client or self.device.ip,
            "question": {"name": domain, "type": query_type},
            "reason": reason,
            "status": "NOERROR",
            "service_name": "",
        }

    @patch("core.adguard.AdGuardClient")
    def test_sync_aggregates_queries_and_does_not_count_cursor_twice(self, client_class):
        entries = [
            self.query(seconds_ago=1, domain="Example.COM."),
            self.query(
                seconds_ago=2,
                domain="example.com",
                reason="FilteredBlackList",
            ),
            self.query(seconds_ago=3, domain="example.com", query_type="AAAA"),
            self.query(
                seconds_ago=4,
                domain="unmatched.example",
                client="192.168.1.99",
            ),
        ]
        client_class.return_value.query_log_config.return_value = {"enabled": True}
        client_class.return_value.query_log.return_value = {"data": entries}

        result = sync_adguard_query_log(self.config)

        self.assertEqual(result["processed"], 4)
        self.assertEqual(result["matched"], 3)
        self.assertEqual(result["unmatched"], 1)
        unmatched = AdGuardUnmatchedClient.objects.get(client="192.168.1.99")
        self.assertEqual(unmatched.query_count, 1)
        self.assertEqual(unmatched.last_domain, "unmatched.example")
        ipv4 = DeviceDNSActivity.objects.get(
            device=self.device,
            domain="example.com",
            query_type="A",
        )
        self.assertEqual(ipv4.query_count, 2)
        self.assertEqual(ipv4.blocked_count, 1)
        self.assertEqual(DeviceDNSActivity.objects.count(), 2)

        second_result = sync_adguard_query_log(AppSettings.load())

        self.assertEqual(second_result["processed"], 0)
        ipv4.refresh_from_db()
        self.assertEqual(ipv4.query_count, 2)

    def test_global_activity_and_unmatched_diagnostics_endpoints(self):
        now = timezone.now()
        DeviceDNSActivity.objects.create(
            device=self.device,
            domain="example.com",
            query_type="A",
            query_count=5,
            blocked_count=2,
            first_seen=now - timedelta(hours=1),
            last_seen=now,
        )
        AdGuardUnmatchedClient.objects.create(
            client="192.168.1.99",
            query_count=4,
            blocked_count=1,
            first_seen=now - timedelta(minutes=20),
            last_seen=now,
            last_domain="unknown.example",
        )

        activity_response = self.viewer_client.get("/api/v1/dns-activity/")
        unmatched_response = self.viewer_client.get(
            "/api/v1/dns-activity/unmatched/"
        )

        self.assertEqual(activity_response.status_code, 200)
        self.assertEqual(activity_response.data["data"][0]["device_name"], self.device.name)
        self.assertEqual(activity_response.data["summary"]["active_devices"], 1)
        self.assertEqual(unmatched_response.status_code, 200)
        self.assertEqual(unmatched_response.data["summary"]["clients"], 1)
        self.assertEqual(unmatched_response.data["data"][0]["client"], "192.168.1.99")

    def test_dns_cleanup_is_independent_and_supports_clean_all(self):
        old = timezone.now() - timedelta(days=100)
        recent = timezone.now() - timedelta(days=2)
        for domain, seen_at in (("old.example", old), ("recent.example", recent)):
            DeviceDNSActivity.objects.create(
                device=self.device,
                domain=domain,
                query_type="A",
                query_count=1,
                first_seen=seen_at,
                last_seen=seen_at,
            )
        AdGuardUnmatchedClient.objects.create(
            client="192.168.1.99",
            query_count=1,
            first_seen=old,
            last_seen=old,
            last_domain="old-unmatched.example",
        )

        response = self.admin_client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "dns_activity", "older_than_days": 90},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["deleted"]["dns_activity"], 1)
        self.assertEqual(
            response.data["data"]["deleted"]["dns_unmatched_clients"], 1
        )
        self.assertEqual(DeviceDNSActivity.objects.count(), 1)

        clean_all_response = self.admin_client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "dns_activity", "clean_all": True},
            format="json",
        )
        self.assertEqual(clean_all_response.status_code, 200)
        self.assertFalse(DeviceDNSActivity.objects.exists())

    def test_general_scheduled_cleanup_does_not_use_dns_retention(self):
        old = timezone.now() - timedelta(days=100)
        DeviceDNSActivity.objects.create(
            device=self.device,
            domain="kept-by-general-cleanup.example",
            query_type="A",
            query_count=1,
            first_seen=old,
            last_seen=old,
        )

        result = cleanup_all_activity(90)

        self.assertEqual(result["deleted"]["dns_activity"], 0)
        self.assertTrue(DeviceDNSActivity.objects.exists())

    def test_settings_hide_password_and_validate_retention(self):
        response = self.admin_client.get("/api/v1/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["adguard_configured"])
        self.assertNotIn("adguard_password", response.data["data"])

        invalid = self.admin_client.put(
            "/api/v1/settings/",
            {"adguard_retention_days": 0},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("adguard_retention_days", invalid.data)

    @patch("core.views.test_adguard_connection")
    def test_admin_can_test_saved_connection_without_resending_password(self, test_connection):
        test_connection.return_value = {
            "version": "0.107.60",
            "running": True,
            "protection_enabled": True,
            "query_log_enabled": True,
        }

        response = self.admin_client.post(
            "/api/v1/integrations/adguard/test/",
            {
                "url": self.config.adguard_url,
                "username": self.config.adguard_username,
                "password": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        test_connection.assert_called_once_with(
            self.config.adguard_url,
            self.config.adguard_username,
            "secret",
        )

    def test_regular_user_cannot_run_manual_sync(self):
        response = self.viewer_client.post("/api/v1/integrations/adguard/sync/")

        self.assertEqual(response.status_code, 403)

    def test_device_activity_endpoint_summarizes_and_filters_domains(self):
        now = timezone.now()
        DeviceDNSActivity.objects.create(
            device=self.device,
            domain="example.com",
            query_type="A",
            query_count=5,
            blocked_count=2,
            first_seen=now - timedelta(hours=1),
            last_seen=now,
            last_reason="FilteredBlackList",
        )
        DeviceDNSActivity.objects.create(
            device=self.device,
            domain="example.com",
            query_type="AAAA",
            query_count=3,
            first_seen=now - timedelta(minutes=30),
            last_seen=now,
        )
        DeviceDNSActivity.objects.create(
            device=self.device,
            domain="allowed.example",
            query_type="A",
            query_count=4,
            first_seen=now - timedelta(minutes=10),
            last_seen=now,
        )

        response = self.viewer_client.get(
            "/api/v1/device/dns-activity/",
            {"id": self.device.id, "blocked": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["domain"], "example.com")
        self.assertEqual(response.data["summary"]["unique_domains"], 2)
        self.assertEqual(response.data["summary"]["total_queries"], 12)
        self.assertEqual(response.data["summary"]["blocked_queries"], 2)

    def test_retention_removes_stale_aggregates(self):
        old = timezone.now() - timedelta(days=100)
        DeviceDNSActivity.objects.create(
            device=self.device,
            domain="old.example",
            query_type="A",
            query_count=1,
            first_seen=old,
            last_seen=old,
        )

        with patch("core.adguard.AdGuardClient") as client_class:
            client_class.return_value.query_log_config.return_value = {"enabled": True}
            client_class.return_value.query_log.return_value = {"data": []}
            result = sync_adguard_query_log(self.config)

        self.assertEqual(result["deleted"], 1)
        self.assertFalse(DeviceDNSActivity.objects.exists())
