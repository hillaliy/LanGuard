from datetime import datetime, timedelta, timezone as datetime_timezone
import hashlib
import hmac
import importlib
import json
import socket
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.cache import cache
from django.db import DatabaseError, OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
import requests
from rest_framework.test import APIClient

from backend.settings import include_internal_hosts, validate_production_settings
from ..datetime_utils import utc_isoformat
from ..management.commands.run_scheduler import load_scan_schedule
from ..models import (
    AppSettings,
    Device,
    DeviceIPAddressAssignment,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
    UserAccess,
)
from ..notifications import (
    format_discord_payload,
    format_webhook_payload,
    notify_event,
    quiet_hours_active,
    retry_failed_notifications,
    send_discord_test,
    send_ntfy_test,
    send_telegram,
    send_telegram_test,
    send_webhook_test,
)
from ..port_guidance import PORT_CATALOG, port_guidance
from ..serializers.devices import device_attention_reasons, device_identity
from ..views.inventory import parse_inventory_datetime
from ..versioning import check_for_version_update, is_newer_version
from ..scanning.discovery import (
    MDNS_SERVICE_HOSTNAME_CACHE,
    detect_web_interface,
    dns_encode_name,
    dns_ptr_names,
    dns_server_reverse_hostname,
    get_hostname,
    hostname_from_device_description,
    llmnr_reverse_hostname,
    mdns_multicast_responses,
    mdns_query_responses,
    mdns_reverse_hostname,
    mdns_service_hostname,
    mdns_service_hostname_map,
    mdns_service_hostnames_from_response,
    mdns_service_hostnames_from_responses,
    mdns_service_types_from_response,
    ssdp_hostname_from_response,
    ssdp_metadata_from_response,
    web_interface_candidates,
)
from ..scanning.events import create_event
from ..scanning.identity import (
    clean_hostname,
    guess_device_identity,
    mismatched_default_haa_hostname,
    preferred_vendor,
)
from ..scanning.lifecycle import (
    STALE_SCAN_ERROR,
    ScanAlreadyRunning,
    active_scan_run,
    claim_scan_run,
    scan_failure_diagnostics,
)
from ..scanning.network import (
    default_gateway_from_proc_route,
    discover_devices,
    local_scanner_interface,
)
from ..scanning.orchestration import scan
from ..scanning.ports import normalize_scan_ports, sync_device_ports
from ..scanning.presence import (
    clear_stale_gateways,
    mark_missing_devices_offline,
)
from ..scanning.ranges import validate_ip_range, validate_ip_ranges
from ..scanning.reconciliation import sync_discovered_device
from ..scanning.vendor import ManufVendorDB, manuf_vendor

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
