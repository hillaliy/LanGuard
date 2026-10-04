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

class SettingsApiTests(TestCase):
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

    def test_settings_endpoint_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/settings/")

        self.assertEqual(response.status_code, 403)

    def test_settings_endpoint_updates_scan_and_notification_settings(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "ip_range": "192.168.1.0/24",
                "scan_interval": 15,
                "time_zone": "Asia/Jerusalem",
                "version_check_interval": 3600,
                "discord_enabled": False,
                "telegram_enabled": True,
                "telegram_api_url": "https://relay.example/telegram/",
                "ntfy_enabled": True,
                "webhook_enabled": True,
                "notify_new_devices": True,
                "notify_device_online": True,
                "notify_device_offline": True,
                "notify_port_changes": True,
                "notify_version_updates": True,
                "notify_speedtest_changes": True,
                "notification_quiet_hours_enabled": True,
                "notification_quiet_hours_start": "23:00",
                "notification_quiet_hours_end": "06:30",
                "notification_quiet_hours_days": ["sun", "mon", "wed"],
                "activity_cleanup_retention_days": 45,
                "discord_webhook": "https://discord.example/webhook",
                "telegram_token": "token",
                "telegram_user_id": "123",
                "ntfy_server_url": "https://ntfy.example",
                "ntfy_topic": "languard",
                "ntfy_priority": 4,
                "webhook_url": "https://automation.example/webhook/languard",
                "webhook_secret": "shared-secret",
                "home_map_layout": {
                    "order": ["Floor", "Bedroom"],
                    "parents": {"Bedroom": "Floor"},
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = AppSettings.load()
        self.assertEqual(config.ip_range, "192.168.1.0/24")
        self.assertEqual(config.scan_ranges, ["192.168.1.0/24"])
        self.assertEqual(config.scan_interval, 15)
        self.assertEqual(config.time_zone, "Asia/Jerusalem")
        self.assertEqual(config.version_check_interval, 3600)
        self.assertFalse(config.discord_enabled)
        self.assertTrue(config.telegram_enabled)
        self.assertEqual(config.telegram_api_url, "https://relay.example/telegram")
        self.assertTrue(config.ntfy_enabled)
        self.assertTrue(config.webhook_enabled)
        self.assertTrue(config.notify_new_devices)
        self.assertTrue(config.notify_device_online)
        self.assertTrue(config.notify_device_offline)
        self.assertTrue(config.notify_port_changes)
        self.assertTrue(config.notify_version_updates)
        self.assertTrue(config.notify_speedtest_changes)
        self.assertTrue(config.notification_quiet_hours_enabled)
        self.assertEqual(config.notification_quiet_hours_start, "23:00")
        self.assertEqual(config.notification_quiet_hours_end, "06:30")
        self.assertEqual(config.notification_quiet_hours_days, ["mon", "wed", "sun"])
        self.assertEqual(config.activity_cleanup_retention_days, 45)
        self.assertEqual(
            config.home_map_layout,
            {"order": ["Floor", "Bedroom"], "parents": {"Bedroom": "Floor"}},
        )
        self.assertEqual(config.discord_webhook, "https://discord.example/webhook")
        self.assertEqual(config.telegram_token, "token")
        self.assertEqual(config.telegram_user_id, "123")
        self.assertEqual(config.ntfy_server_url, "https://ntfy.example")
        self.assertEqual(config.ntfy_topic, "languard")
        self.assertEqual(config.ntfy_priority, 4)
        self.assertEqual(
            config.webhook_url,
            "https://automation.example/webhook/languard",
        )
        self.assertEqual(config.webhook_secret, "shared-secret")
        self.assertNotIn("discord_webhook", response.data["data"])
        self.assertNotIn("telegram_token", response.data["data"])
        self.assertEqual(response.data["data"]["telegram_user_id"], "123")
        self.assertFalse(response.data["data"]["discord_enabled"])
        self.assertTrue(response.data["data"]["telegram_enabled"])
        self.assertEqual(
            response.data["data"]["telegram_api_url"],
            "https://relay.example/telegram",
        )
        self.assertTrue(response.data["data"]["ntfy_enabled"])
        self.assertTrue(response.data["data"]["ntfy_configured"])
        self.assertTrue(response.data["data"]["webhook_enabled"])
        self.assertTrue(response.data["data"]["webhook_configured"])
        self.assertTrue(response.data["data"]["webhook_signature_configured"])
        self.assertNotIn("webhook_secret", response.data["data"])
        self.assertTrue(response.data["data"]["discord_configured"])
        self.assertEqual(response.data["data"]["version_check_interval"], 3600)
        self.assertTrue(response.data["data"]["notify_device_online"])
        self.assertTrue(response.data["data"]["notify_device_offline"])
        self.assertTrue(response.data["data"]["notify_port_changes"])
        self.assertTrue(response.data["data"]["notify_version_updates"])
        self.assertTrue(response.data["data"]["notify_speedtest_changes"])
        self.assertTrue(response.data["data"]["notification_quiet_hours_enabled"])
        self.assertEqual(response.data["data"]["notification_quiet_hours_start"], "23:00")
        self.assertEqual(response.data["data"]["notification_quiet_hours_end"], "06:30")
        self.assertEqual(
            response.data["data"]["notification_quiet_hours_days"],
            ["mon", "wed", "sun"],
        )
        self.assertEqual(response.data["data"]["activity_cleanup_retention_days"], 45)
        self.assertEqual(
            response.data["data"]["home_map_layout"],
            {"order": ["Floor", "Bedroom"], "parents": {"Bedroom": "Floor"}},
        )

    def test_settings_endpoint_keeps_telegram_token_secret_and_preserves_blank(self):
        config = AppSettings.load()
        config.telegram_token = "saved-bot-token"
        config.telegram_user_id = "123456"
        config.save(update_fields=["telegram_token", "telegram_user_id"])

        response = self.client.put(
            "/api/v1/settings/",
            {
                "telegram_token": "",
                "telegram_user_id": "654321",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        self.assertEqual(config.telegram_token, "saved-bot-token")
        self.assertEqual(config.telegram_user_id, "654321")
        self.assertTrue(response.data["data"]["telegram_configured"])
        self.assertNotIn("telegram_token", response.data["data"])

        get_response = self.client.get("/api/v1/settings/")
        self.assertEqual(get_response.status_code, 200)
        self.assertNotIn("telegram_token", get_response.data["data"])

    def test_settings_endpoint_rejects_invalid_telegram_api_url(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"telegram_api_url": "ftp://user:secret@relay.example/api?token=value"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("telegram_api_url", response.data)

    def test_settings_endpoint_keeps_discord_webhook_secret_and_preserves_blank(self):
        config = AppSettings.load()
        config.discord_webhook = "https://discord.example/saved-webhook"
        config.save(update_fields=["discord_webhook"])

        response = self.client.put(
            "/api/v1/settings/",
            {"discord_webhook": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        self.assertEqual(
            config.discord_webhook,
            "https://discord.example/saved-webhook",
        )
        self.assertTrue(response.data["data"]["discord_configured"])
        self.assertNotIn("discord_webhook", response.data["data"])

        get_response = self.client.get("/api/v1/settings/")
        self.assertEqual(get_response.status_code, 200)
        self.assertNotIn("discord_webhook", get_response.data["data"])

    def test_settings_endpoint_saves_multiple_network_ranges(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "scan_ranges": ["192.168.1.4/24", "192.168.20.0/24"],
                "scan_range_labels": {
                    "192.168.1.4/24": "Main LAN",
                    "192.168.20.0/24": "IoT",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = AppSettings.load()
        self.assertEqual(config.ip_range, "192.168.1.0/24")
        self.assertEqual(
            config.scan_ranges,
            ["192.168.1.0/24", "192.168.20.0/24"],
        )
        self.assertEqual(
            config.scan_range_labels,
            {
                "192.168.1.0/24": "Main LAN",
                "192.168.20.0/24": "IoT",
            },
        )
        self.assertEqual(response.data["data"]["scan_ranges"], config.scan_ranges)
        self.assertEqual(
            response.data["data"]["scan_range_labels"],
            config.scan_range_labels,
        )

    def test_settings_endpoint_rejects_blank_network_name(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "scan_ranges": ["192.168.1.0/24"],
                "scan_range_labels": {"192.168.1.0/24": ""},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("scan_range_labels", response.data)

    def test_settings_endpoint_rejects_duplicate_network_names(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "scan_ranges": ["192.168.1.0/24", "192.168.20.0/24"],
                "scan_range_labels": {
                    "192.168.1.0/24": "IoT",
                    "192.168.20.0/24": "iot",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("scan_range_labels", response.data)

    @override_settings(SCAN_MAX_HOSTS=1024)
    def test_settings_endpoint_accepts_1024_address_network_range(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"scan_ranges": ["192.168.0.0/22"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["scan_ranges"], ["192.168.0.0/22"])
        self.assertEqual(response.data["data"]["scan_max_hosts"], 1024)

    @override_settings(SCAN_MAX_HOSTS=1024)
    def test_settings_endpoint_rejects_more_than_1024_addresses(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"scan_ranges": ["192.168.0.0/21"]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("scan_ranges", response.data)

    def test_settings_endpoint_rejects_overlapping_network_ranges(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "scan_ranges": ["192.168.1.0/24", "192.168.1.128/25"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("scan_ranges", response.data)
        self.assertEqual(
            response.data["notification"]["message"],
            "Network ranges must not overlap. CIDR entries are normalized to their "
            "network boundary; use one larger range instead of adding ranges it "
            "already contains.",
        )

    def test_settings_endpoint_rejects_short_version_check_interval(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"version_check_interval": 30},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("version_check_interval", response.data)

    def test_settings_endpoint_saves_and_masks_speedtest_tracker_token(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "speedtest_tracker_enabled": True,
                "speedtest_tracker_url": "http://192.168.1.5:8080",
                "speedtest_tracker_api_token": "private-api-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = AppSettings.load()
        self.assertTrue(config.speedtest_tracker_enabled)
        self.assertEqual(config.speedtest_tracker_api_token, "private-api-token")
        self.assertTrue(response.data["data"]["speedtest_tracker_configured"])
        self.assertNotIn("speedtest_tracker_api_token", response.data["data"])

        keep_response = self.client.put(
            "/api/v1/settings/",
            {
                "speedtest_tracker_url": "http://192.168.1.6:8080",
                "speedtest_tracker_api_token": "",
            },
            format="json",
        )
        config.refresh_from_db()
        self.assertEqual(keep_response.status_code, 200)
        self.assertEqual(config.speedtest_tracker_api_token, "private-api-token")

    def test_settings_endpoint_requires_speedtest_tracker_connection_details(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"speedtest_tracker_enabled": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("speedtest_tracker_url", response.data)

    def test_settings_endpoint_rejects_enabled_webhook_without_url(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"webhook_enabled": True, "webhook_url": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("webhook_url", response.data)

    def test_settings_endpoint_keeps_or_clears_saved_webhook_secret_explicitly(self):
        config = AppSettings.load()
        config.webhook_secret = "saved-secret"
        config.save(update_fields=["webhook_secret"])

        keep_response = self.client.put(
            "/api/v1/settings/",
            {"webhook_secret": ""},
            format="json",
        )
        config.refresh_from_db()

        self.assertEqual(keep_response.status_code, 200)
        self.assertEqual(config.webhook_secret, "saved-secret")

        clear_response = self.client.put(
            "/api/v1/settings/",
            {"clear_webhook_secret": True},
            format="json",
        )
        config.refresh_from_db()

        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(config.webhook_secret, "")
        self.assertFalse(clear_response.data["data"]["webhook_signature_configured"])
        self.assertNotIn("clear_webhook_secret", clear_response.data["data"])

    def test_settings_endpoint_rejects_bad_quiet_hours(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"notification_quiet_hours_start": "23:00:00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("notification_quiet_hours_start", response.data)

    def test_settings_endpoint_rejects_bad_quiet_hours_days(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"notification_quiet_hours_days": ["mon", "someday"]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("notification_quiet_hours_days", response.data)

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_settings_endpoint_rejects_unsafe_scan_range(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"ip_range": "8.8.8.0/24"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ip_range", response.data)

    def test_settings_endpoint_rejects_bad_timezone(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"time_zone": "Bad/Timezone"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("time_zone", response.data)
