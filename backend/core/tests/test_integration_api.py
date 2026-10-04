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

class IntegrationApiTests(TestCase):
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

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_latest_result_is_normalized_and_cached(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "id": 42,
                    "download_bits": 500_000_000,
                    "upload_bits": 100_000_000,
                    "download_bits_human": "500 Mbps",
                    "upload_bits_human": "100 Mbps",
                    "ping": 8.4,
                    "healthy": True,
                    "status": "completed",
                    "created_at": "2026-09-02T06:00:00Z",
                    "data": {"packetLoss": 0},
                }
            ),
        )
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        first = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")
        second = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["data"]["download_mbps"], 500.0)
        self.assertEqual(first.data["data"]["upload_mbps"], 100.0)
        self.assertEqual(first.data["data"]["packet_loss_percent"], 0.0)
        self.assertTrue(first.data["integration"]["available"])
        self.assertFalse(first.data["integration"]["cached"])
        self.assertTrue(second.data["integration"]["cached"])
        self.assertNotIn("private-api-token", str(first.data))
        get.assert_called_once()

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_refresh_bypasses_cache(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={"id": 1, "status": "completed"}),
        )
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        self.client.get("/api/v1/integrations/speedtest-tracker/latest/")
        response = self.client.get(
            "/api/v1/integrations/speedtest-tracker/latest/",
            {"refresh": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["integration"]["cached"])
        self.assertEqual(get.call_count, 2)

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_unavailable_does_not_fail_dashboard_request(self, get):
        cache.clear()
        get.side_effect = requests.Timeout("private upstream detail")
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        response = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["data"])
        self.assertFalse(response.data["integration"]["available"])
        self.assertNotIn("private", str(response.data))

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_connection_test_uses_saved_token(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={"id": 1, "status": "completed"}),
        )
        config = AppSettings.load()
        config.speedtest_tracker_api_token = "saved-api-token"
        config.save(update_fields=["speedtest_tracker_api_token"])

        response = self.client.post(
            "/api/v1/integrations/speedtest-tracker/test/",
            {"url": "http://192.168.1.5:8080"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["notification"]["title"], "Speedtest Tracker connected")
        self.assertNotIn("saved-api-token", str(response.data))

    def test_speedtest_tracker_connection_test_requires_admin_user(self):
        regular_user = User.objects.create_user(username="speed-viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/integrations/speedtest-tracker/test/",
            {
                "url": "http://192.168.1.5:8080",
                "api_token": "private-api-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_speedtest_tracker_latest_requires_authentication(self):
        anonymous_client = APIClient()

        response = anonymous_client.get(
            "/api/v1/integrations/speedtest-tracker/latest/"
        )

        self.assertIn(response.status_code, {401, 403})
