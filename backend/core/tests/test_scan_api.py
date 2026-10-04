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

class ScanApiTests(TestCase):
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

    def test_scan_endpoints_require_authentication(self):
        client = APIClient()

        response = client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 401)

    def test_scan_status_endpoint_returns_latest_scan_and_counters(self):
        self.scan_run.started_at = timezone.now() - timedelta(minutes=2)
        self.scan_run.finished_at = timezone.now()
        self.scan_run.save(update_fields=["started_at", "finished_at"])
        Device.objects.create(
            name="Stale phone",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
            online=False,
            status=Device.Status.ONLINE,
        )
        Device.objects.create(
            name="Offline camera",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
            online=True,
            status=Device.Status.OFFLINE,
        )
        Device.objects.create(
            name="Visitor phone",
            ip="192.168.1.23",
            mac="dd:dd:dd:dd:dd:dd",
            known=True,
            is_visitor=True,
            status=Device.Status.ONLINE,
        )
        Device.objects.create(
            name="Archived tablet",
            ip="192.168.1.24",
            mac="ee:ee:ee:ee:ee:ee",
            archived=True,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertEqual(response.data["counters"]["all_devices"], 3)
        self.assertEqual(response.data["counters"]["online_devices"], 2)
        self.assertEqual(response.data["counters"]["offline_devices"], 1)
        self.assertEqual(response.data["counters"]["visitor_devices"], 1)
        self.assertEqual(response.data["counters"]["online_visitors"], 1)
        self.assertEqual(response.data["counters"]["archived_devices"], 1)
        self.assertEqual(response.data["counters"]["unnotified_events"], 1)
        self.assertEqual(response.data["time_zone"], "UTC")
        self.assertEqual(response.data["network_ranges"], ["192.168.1.0/24"])
        self.assertEqual(
            response.data["network_range_labels"],
            {"192.168.1.0/24": "Primary network"},
        )
        self.assertEqual(
            response.data["integrations"]["adguard"],
            {"enabled": False, "configured": False},
        )
        self.assertEqual(
            response.data["integrations"]["docker"],
            {"configured": False},
        )
        self.assertFalse(response.data["visibility"]["is_scanning"])
        self.assertEqual(response.data["visibility"]["current_range"], "192.168.1.0/24")
        self.assertEqual(
            response.data["visibility"]["current_ranges"],
            ["192.168.1.0/24"],
        )
        self.assertTrue(response.data["data"]["started_at"].endswith("Z"))
        self.assertTrue(response.data["data"]["finished_at"].endswith("Z"))
        self.assertTrue(response.data["visibility"]["started_at"].endswith("Z"))
        self.assertTrue(response.data["visibility"]["finished_at"].endswith("Z"))
        self.assertGreaterEqual(response.data["visibility"]["duration_seconds"], 119)

    def test_scan_status_exposes_safe_active_adguard_state(self):
        config = AppSettings.load()
        config.adguard_enabled = True
        config.adguard_url = "http://192.168.1.2:3000"
        config.adguard_username = "admin"
        config.adguard_password = "secret-password"
        config.save()

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["integrations"]["adguard"],
            {"enabled": True, "configured": True},
        )
        self.assertNotIn("adguard_url", str(response.data))
        self.assertNotIn("secret-password", str(response.data))

    def test_scan_status_endpoint_returns_active_scan_visibility(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.2.0/24",
            status=ScanRun.Status.RUNNING,
            source=ScanRun.Source.SCHEDULED,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_scan"]["id"], running_scan.id)
        self.assertTrue(response.data["visibility"]["is_scanning"])
        self.assertEqual(response.data["visibility"]["source"], "scheduled")
        self.assertEqual(response.data["visibility"]["current_range"], "192.168.2.0/24")
        self.assertTrue(response.data["active_scan"]["started_at"].endswith("Z"))
        self.assertTrue(response.data["visibility"]["started_at"].endswith("Z"))

    def test_scan_status_endpoint_keeps_latest_completed_scan_during_running_scan(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertEqual(response.data["active_scan"]["id"], running_scan.id)

    def test_scan_status_endpoint_finishes_superseded_running_scan(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
            started_at=timezone.now() - timedelta(minutes=30),
        )
        self.scan_run.started_at = timezone.now() - timedelta(minutes=5)
        self.scan_run.finished_at = timezone.now() - timedelta(minutes=1)
        self.scan_run.save(update_fields=["started_at", "finished_at"])

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertIsNone(response.data["active_scan"])
        self.assertFalse(response.data["visibility"]["is_scanning"])
        self.assertEqual(
            response.data["visibility"]["finished_at"],
            utc_isoformat(self.scan_run.finished_at),
        )
        running_scan.refresh_from_db()
        self.assertEqual(running_scan.status, ScanRun.Status.FAILED)
        self.assertEqual(
            running_scan.error,
            "Scan was superseded by a newer completed scan.",
        )

    def test_scan_metadata_changes_do_not_invalidate_attention_acknowledgement(self):
        self.device.known = True
        self.device.vendor = "Original vendor"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=8080, protocol="tcp", open=True)
        self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"acknowledge_attention": True},
            format="json",
        )

        self.device.vendor = "Updated vendor"
        self.device.hostname = "matter-hub.local"
        self.device.status = Device.Status.RECENTLY_SEEN
        self.device.missed_scans = 1
        self.device.save(
            update_fields=["vendor", "hostname", "status", "missed_scans"]
        )

        device = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertEqual(device["risk_level"], "medium")
        self.assertTrue(device["attention_acknowledged"])
        self.assertFalse(device["needs_attention"])

    def test_scan_runs_endpoint_returns_history(self):
        response = self.client.get("/api/v1/scan/runs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["id"], self.scan_run.id)
        self.assertTrue(response.data["data"][0]["started_at"].endswith("Z"))
        self.assertEqual(response.data["pagination"]["count"], 1)

    def test_scan_runs_endpoint_filters_by_status(self):
        ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.FAILED,
            error="failed",
        )

        response = self.client.get("/api/v1/scan/runs/", {"status": "failed"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["status"], ScanRun.Status.FAILED)

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_scan_now_rejects_public_ranges(self):
        response = self.client.post(
            "/api/v1/scan/",
            {"ip_range": "8.8.8.0/24"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ip_range", response.data)

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    @patch("core.views.scans.scan")
    def test_scan_now_uses_saved_default_range(self, scan_mock):
        AppSettings.objects.create(ip_range="192.168.1.0/24", scan_interval=10)
        scan_mock.return_value = self.scan_run

        response = self.client.post("/api/v1/scan/", {}, format="json")

        self.assertEqual(response.status_code, 202)
        scan_mock.assert_called_once_with(
            ["192.168.1.0/24"],
            source=ScanRun.Source.MANUAL,
        )

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    @patch("core.views.scans.scan")
    def test_scan_now_uses_saved_network_ranges(self, scan_mock):
        config = AppSettings.load()
        config.ip_range = "192.168.1.0/24"
        config.scan_ranges = ["192.168.1.0/24", "192.168.20.0/24"]
        config.save(update_fields=["ip_range", "scan_ranges"])
        scan_mock.return_value = self.scan_run

        response = self.client.post("/api/v1/scan/", {}, format="json")

        self.assertEqual(response.status_code, 202)
        scan_mock.assert_called_once_with(
            ["192.168.1.0/24", "192.168.20.0/24"],
            source=ScanRun.Source.MANUAL,
        )

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_scan_now_returns_conflict_while_another_scan_is_running(self):
        active_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            scan_ranges=["192.168.1.0/24"],
            source=ScanRun.Source.SCHEDULED,
        )

        response = self.client.post("/api/v1/scan/", {}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["status"], "Conflict")
        self.assertEqual(response.data["data"]["id"], active_scan.id)
        self.assertIn("scheduled scan is already running", response.data["detail"])

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    @patch("core.views.scans.scan")
    def test_scan_now_returns_json_when_scanner_lacks_permissions(self, scan_mock):
        scan_mock.side_effect = Exception(
            "Permission denied: could not open /dev/bpf0. Make sure to be running Scapy as root ! (sudo)"
        )

        response = self.client.post(
            "/api/v1/scan/",
            {"ip_range": "192.168.1.0/24"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "Error")
        self.assertIn("packet-capture permissions", response.data["info"])

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_validate_ip_range_rejects_large_ranges(self):
        with self.assertRaises(ValueError):
            validate_ip_range("192.168.0.0/16")

    @override_settings(PORT_SCAN_MAX_PORTS=2)
    def test_normalize_scan_ports_enforces_port_count_limit(self):
        with self.assertRaises(ValueError):
            normalize_scan_ports([22, 80, 443])
