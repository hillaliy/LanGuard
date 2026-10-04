from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from backend.settings import include_internal_hosts, validate_production_settings
from ..models import (
    AppSettings,
    NetworkEvent,
)
from ..versioning import check_for_version_update, is_newer_version

class ProductionSettingsTests(SimpleTestCase):
    def test_internal_health_check_hosts_are_always_allowed(self):
        self.assertEqual(
            include_internal_hosts(["languard.local", "127.0.0.1"]),
            ["languard.local", "127.0.0.1", "localhost", "[::1]"],
        )

    def test_development_allows_local_defaults(self):
        validate_production_settings(
            "development",
            "unsafe-dev-secret-key",
            True,
            ["localhost", "127.0.0.1"],
        )

    def test_production_rejects_unsafe_defaults(self):
        with self.assertRaises(ImproperlyConfigured) as context:
            validate_production_settings(
                "production",
                "change-me",
                True,
                ["localhost", "127.0.0.1"],
            )

        message = str(context.exception)
        self.assertIn("SECRET_KEY", message)
        self.assertIn("DEBUG", message)
        self.assertIn("LAN IP", message)

    def test_production_accepts_strong_local_network_config(self):
        validate_production_settings(
            "production",
            "a-strong-production-secret-key-value",
            False,
            ["languard.local", "192.168.1.10"],
        )
class ApiDocsAccessTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_openapi_schema_is_public(self):
        response = self.client.get("/api/schema/")

        self.assertEqual(response.status_code, 200)

    def test_swagger_ui_is_public(self):
        response = self.client.get("/api/schema/swagger/")

        self.assertEqual(response.status_code, 200)

    def test_redoc_is_public(self):
        response = self.client.get("/api/schema/redoc/")

        self.assertEqual(response.status_code, 200)
class VersionStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(
        APP_VERSION="1.0.2",
        LATEST_VERSION_URL="https://example.test/VERSION",
        VERSION_CHECK_TIMEOUT=1,
    )
    @patch("core.versioning.urllib.request.urlopen")
    def test_version_endpoint_returns_latest_public_version(self, urlopen):
        response_mock = Mock()
        response_mock.read.return_value = b"1.0.3\n"
        urlopen.return_value.__enter__.return_value = response_mock

        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["current_version"], "1.0.2")
        self.assertEqual(response.data["data"]["latest_version"], "1.0.3")
        self.assertEqual(response.data["data"]["check_interval_seconds"], 21600)

    @override_settings(
        APP_VERSION="1.0.2",
        LATEST_VERSION_URL="https://example.test/package.json",
        VERSION_CHECK_TIMEOUT=1,
    )
    @patch("core.versioning.urllib.request.urlopen")
    def test_version_endpoint_accepts_legacy_json_source(self, urlopen):
        response_mock = Mock()
        response_mock.read.return_value = b'{"version": "1.0.3"}'
        urlopen.return_value.__enter__.return_value = response_mock

        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["latest_version"], "1.0.3")

    @override_settings(APP_VERSION="1.0.2", LATEST_VERSION_URL="")
    def test_version_endpoint_uses_saved_check_interval(self):
        AppSettings.objects.create(version_check_interval=1800)

        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["check_interval_seconds"], 1800)

    @override_settings(APP_VERSION="1.0.2", LATEST_VERSION_URL="")
    def test_version_endpoint_falls_back_without_latest_source(self):
        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["current_version"], "1.0.2")
        self.assertIsNone(response.data["data"]["latest_version"])

    def test_version_comparison_handles_prefixes_and_different_lengths(self):
        self.assertTrue(is_newer_version("v1.10.0", "1.9"))
        self.assertFalse(is_newer_version("1.10", "v1.10.0"))
        self.assertFalse(is_newer_version("not-a-version", "1.0.0"))

    @override_settings(APP_VERSION="1.0.2")
    @patch("core.versioning.notify_event")
    @patch("core.versioning.fetch_latest_version", return_value="v1.1.0")
    def test_version_update_notification_is_sent_once_per_version(
        self,
        fetch_latest_version,
        notify_event_mock,
    ):
        config = AppSettings.objects.create(
            notify_version_updates=True,
            discord_enabled=True,
            discord_webhook="https://discord.example/webhook",
        )
        notify_event_mock.return_value = [Mock()]

        first_result = check_for_version_update()
        second_result = check_for_version_update()

        self.assertEqual(first_result["status"], "notified")
        self.assertEqual(second_result["status"], "already_notified")
        self.assertEqual(fetch_latest_version.call_count, 2)
        notify_event_mock.assert_called_once()
        event = NetworkEvent.objects.get(
            event_type=NetworkEvent.EventType.VERSION_AVAILABLE
        )
        self.assertIsNone(event.device)
        self.assertEqual(event.metadata["current_version"], "1.0.2")
        self.assertEqual(event.metadata["latest_version"], "1.1.0")
        self.assertEqual(
            event.metadata["release_url"],
            "https://github.com/hillaliy/LanGuard/releases/tag/v1.1.0",
        )
        config.refresh_from_db()
        self.assertEqual(config.last_notified_version, "1.1.0")

    @override_settings(APP_VERSION="1.0.2")
    @patch("core.versioning.fetch_latest_version", return_value="1.1.0")
    def test_version_update_waits_for_a_configured_channel(self, _):
        AppSettings.objects.create(notify_version_updates=True)

        result = check_for_version_update()

        self.assertEqual(result["status"], "no_channels")
        self.assertFalse(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.VERSION_AVAILABLE
            ).exists()
        )
class HealthStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_endpoint_is_public_and_checks_database(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

    @patch("core.views.health.connection.cursor", side_effect=DatabaseError("unavailable"))
    def test_health_endpoint_reports_database_failure(self, cursor):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"status": "unavailable"})
