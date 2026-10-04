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

class MaintenanceApiTests(TestCase):
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

    def test_diagnostics_export_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/diagnostics/export/")

        self.assertEqual(response.status_code, 403)

    def test_diagnostics_export_omits_secrets_and_device_identifiers(self):
        config = AppSettings.load()
        config.discord_webhook = "https://discord.example/super-secret-webhook"
        config.telegram_token = "super-secret-bot-token"
        config.telegram_user_id = "987654321"
        config.webhook_enabled = True
        config.webhook_url = "https://automation.example/private-webhook"
        config.webhook_secret = "super-secret-signing-key"
        config.adguard_enabled = True
        config.adguard_url = "http://10.20.30.40:3000"
        config.adguard_username = "private-admin"
        config.adguard_password = "super-secret-password"
        config.adguard_last_error = "Connection failed at http://10.20.30.40/private"
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://10.20.30.50:8080"
        config.speedtest_tracker_api_token = "super-secret-speedtest-token"
        config.save()
        self.scan_run.error = "Failed on 192.168.1.20 with aa:aa:aa:aa:aa:aa"
        self.scan_run.failure_code = "database_locked"
        self.scan_run.failure_type = "OperationalError"
        self.scan_run.failure_stage = "device_sync"
        self.scan_run.failure_fingerprint = "0123456789abcdef"
        self.scan_run.save(
            update_fields=[
                "error",
                "failure_code",
                "failure_type",
                "failure_stage",
                "failure_fingerprint",
            ]
        )
        self.delivery.error = (
            "POST https://api.telegram.org/botsuper-secret-bot-token/sendMessage failed"
        )
        self.delivery.save(update_fields=["error"])

        response = self.client.get("/api/v1/diagnostics/export/")

        self.assertEqual(response.status_code, 200)
        serialized = str(response.data)
        for private_value in (
            "super-secret-webhook",
            "super-secret-bot-token",
            "super-secret-password",
            "super-secret-signing-key",
            "private-webhook",
            "private-admin",
            "10.20.30.40",
            "10.20.30.50",
            "super-secret-speedtest-token",
            "192.168.1.20",
            "aa:aa:aa:aa:aa:aa",
            "Laptop",
        ):
            self.assertNotIn(private_value, serialized)
        self.assertEqual(
            response.data["data"]["report"]["report"]["format"],
            "languard-diagnostics",
        )
        diagnostics = response.data["data"]["report"]
        self.assertEqual(diagnostics["report"]["format_version"], 2)
        latest_scan = diagnostics["latest_scans"][0]
        self.assertEqual(latest_scan["failure_code"], "database_locked")
        self.assertEqual(latest_scan["failure_type"], "OperationalError")
        self.assertEqual(latest_scan["failure_stage"], "device_sync")
        self.assertEqual(latest_scan["failure_fingerprint"], "0123456789abcdef")
        configuration = response.data["data"]["report"]["configuration"]
        self.assertTrue(configuration["speedtest_tracker_enabled"])
        self.assertTrue(configuration["speedtest_tracker_configured"])
        self.assertIn("notification", response.data)

    def test_old_raw_errors_are_sanitized_in_api_responses(self):
        self.scan_run.error = "Internal path /private/app and 192.168.1.20"
        self.scan_run.save(update_fields=["error"])
        self.delivery.error = "https://discord.example/private-webhook"
        self.delivery.save(update_fields=["error"])

        scans = self.client.get("/api/v1/scan/runs/").data
        deliveries = self.client.get("/api/v1/notifications/").data

        self.assertNotIn("/private/app", str(scans))
        self.assertNotIn("192.168.1.20", str(scans))
        self.assertNotIn("private-webhook", str(deliveries))

    def test_maintenance_cleanup_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": 30},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_maintenance_cleanup_deletes_old_events_only(self):
        old_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.SUCCESS,
            started_at=timezone.now() - timedelta(days=400),
            finished_at=timezone.now() - timedelta(days=400),
        )
        old_event = NetworkEvent.objects.create(
            scan_run=old_scan,
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            message="Laptop went offline",
            created_at=timezone.now() - timedelta(days=400),
        )
        old_delivery = NotificationDelivery.objects.create(
            event=old_event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.SENT,
            created_at=timezone.now() - timedelta(days=400),
        )
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
            started_at=timezone.now() - timedelta(days=400),
        )

        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["target"], "events")
        self.assertEqual(response.data["data"]["deleted"]["events"], 1)
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 0)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 0)
        self.assertFalse(NetworkEvent.objects.filter(id=old_event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=old_delivery.id).exists())
        old_delivery.refresh_from_db()
        self.assertIsNone(old_delivery.event_id)
        self.assertTrue(ScanRun.objects.filter(id=old_scan.id).exists())
        self.assertTrue(ScanRun.objects.filter(id=running_scan.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())
        self.assertTrue(ScanRun.objects.filter(id=self.scan_run.id).exists())

    def test_maintenance_cleanup_clean_all_deletes_current_events(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "clean_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["clean_all"])
        self.assertEqual(response.data["data"]["deleted"]["events"], 1)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 0)
        self.assertFalse(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())
        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.event_id)

    def test_maintenance_cleanup_clean_all_deletes_current_scan_runs(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "scan_runs", "clean_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["clean_all"])
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 1)
        self.assertFalse(ScanRun.objects.filter(id=self.scan_run.id).exists())

    def test_maintenance_cleanup_clean_all_deletes_current_notifications(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "notifications", "clean_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["clean_all"])
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 1)
        self.assertFalse(NotificationDelivery.objects.filter(id=self.delivery.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())

    def test_maintenance_cleanup_rejects_zero_day_retention(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": 0},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("older_than_days", response.data)

    def test_maintenance_cleanup_deletes_old_scan_runs_only(self):
        old_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.SUCCESS,
            started_at=timezone.now() - timedelta(days=400),
            finished_at=timezone.now() - timedelta(days=400),
        )
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
            started_at=timezone.now() - timedelta(days=400),
        )

        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "scan_runs", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["target"], "scan_runs")
        self.assertEqual(response.data["data"]["deleted"]["events"], 0)
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 1)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 0)
        self.assertFalse(ScanRun.objects.filter(id=old_scan.id).exists())
        self.assertTrue(ScanRun.objects.filter(id=running_scan.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())

    def test_maintenance_cleanup_deletes_old_notifications_only(self):
        old_delivery = NotificationDelivery.objects.create(
            event=self.event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.SENT,
            created_at=timezone.now() - timedelta(days=400),
        )

        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "notifications", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["target"], "notifications")
        self.assertEqual(response.data["data"]["deleted"]["events"], 0)
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 0)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 1)
        self.assertFalse(NotificationDelivery.objects.filter(id=old_delivery.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())

    def test_maintenance_cleanup_rejects_invalid_retention(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": -1},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("older_than_days", response.data)

    def test_maintenance_cleanup_rejects_invalid_target(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "devices", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("target", response.data)
