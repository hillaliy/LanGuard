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

class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_first_registered_user_becomes_admin(self):
        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "admin",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_staff"])
        self.assertTrue(response.data["is_superuser"])
        user = User.objects.get(username="admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_registration_is_closed_after_first_user_exists(self):
        User.objects.create_user(username="admin", password="password")

        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "viewer",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="viewer").exists())

    def test_setup_status_reports_registration_open(self):
        response = self.client.get("/api/v1/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["registration_open"])

    def test_setup_status_reports_registration_closed_after_user_exists(self):
        User.objects.create_user(username="admin", password="password")

        response = self.client.get("/api/v1/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["registration_open"])

    def test_login_returns_role_flags(self):
        User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
            is_superuser=True,
        )

        response = self.client.post(
            "/api/v1/login/",
            {"username": "admin", "password": "password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])
        self.assertTrue(response.data["is_superuser"])

    def test_logout_requires_authentication(self):
        response = self.client.post("/api/v1/logout/")

        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_token(self):
        user = User.objects.create_user(username="admin", password="password")
        login_response = self.client.post(
            "/api/v1/login/",
            {"username": "admin", "password": "password"},
            format="json",
        )
        token = login_response.data["token"]
        token_client = APIClient()
        token_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        response = token_client.post("/api/v1/logout/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["notification"]["title"], "Logged off")
        self.assertFalse(Token.objects.filter(user=user).exists())
        protected_response = token_client.get("/api/v1/scan/status/")
        self.assertEqual(protected_response.status_code, 401)
