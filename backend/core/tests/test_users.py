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

class UserApiTests(TestCase):
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

    def test_users_endpoint_lists_users(self):
        response = self.client.get("/api/v1/users/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["username"], "admin")
        self.assertNotIn("password", response.data["data"][0])

    def test_users_endpoint_regular_user_lists_only_self(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/users/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["username"], "viewer")

    def test_users_endpoint_regular_user_updates_self_only(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.put(
            f"/api/v1/users/?id={regular_user.id}",
            {
                "username": "viewer-updated",
                "first_name": "yossi",
                "last_name": "user",
                "is_staff": True,
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        regular_user.refresh_from_db()
        self.assertEqual(regular_user.username, "viewer-updated")
        self.assertEqual(regular_user.first_name, "Yossi")
        self.assertEqual(regular_user.last_name, "User")
        self.assertFalse(regular_user.is_staff)
        self.assertTrue(regular_user.is_active)

    def test_users_endpoint_regular_user_cannot_edit_other_users(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.put(
            f"/api/v1/users/?id={self.user.id}",
            {"username": "admin-changed"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "admin")

    def test_users_endpoint_regular_user_cannot_create_or_delete_users(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        create_response = regular_client.post(
            "/api/v1/users/",
            {
                "username": "other",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )
        delete_response = regular_client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_users_endpoint_creates_user(self):
        response = self.client.post(
            "/api/v1/users/",
            {
                "username": "viewer",
                "password": "secret-password",
                "password_confirm": "secret-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="viewer").exists())
        self.assertEqual(response.data["data"]["username"], "viewer")

    def test_admin_can_assign_user_capabilities(self):
        response = self.client.post(
            "/api/v1/users/",
            {
                "username": "viewer",
                "password": "secret-password",
                "password_confirm": "secret-password",
                "can_edit_devices": False,
                "can_edit_home_map": True,
                "can_run_scans": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["data"]["can_edit_devices"])
        self.assertTrue(response.data["data"]["can_edit_home_map"])
        self.assertFalse(response.data["data"]["can_run_scans"])

    def test_regular_user_cannot_change_own_capabilities(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        UserAccess.objects.create(
            user=regular_user,
            can_edit_devices=False,
            can_edit_home_map=False,
            can_run_scans=False,
        )
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.put(
            f"/api/v1/users/?id={regular_user.id}",
            {
                "can_edit_devices": True,
                "can_edit_home_map": True,
                "can_run_scans": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        access = UserAccess.objects.get(user=regular_user)
        self.assertFalse(access.can_edit_devices)
        self.assertFalse(access.can_edit_home_map)
        self.assertFalse(access.can_run_scans)

    def test_restricted_user_can_view_but_cannot_edit_devices(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        UserAccess.objects.create(user=regular_user, can_edit_devices=False)
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        get_response = regular_client.get("/api/v1/device/", {"id": self.device.id})
        put_response = regular_client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"name": "Changed"},
            format="json",
        )
        delete_response = regular_client.delete(f"/api/v1/device/?id={self.device.id}")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(put_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Laptop")

    def test_restricted_user_cannot_bulk_update_devices(self):
        regular_user = User.objects.create_user(username="bulk-viewer", password="password")
        UserAccess.objects.create(user=regular_user, can_edit_devices=False)
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id], "known": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        response = regular_client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id], "acknowledge_attention": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_restricted_user_cannot_edit_home_map_or_run_scan(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        UserAccess.objects.create(
            user=regular_user,
            can_edit_home_map=False,
            can_run_scans=False,
        )
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        get_response = regular_client.get("/api/v1/home-map-layout/")
        put_response = regular_client.put(
            "/api/v1/home-map-layout/",
            {"layout": {"order": ["Office"], "parents": {}}},
            format="json",
        )
        scan_response = regular_client.post("/api/v1/scan/", {}, format="json")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(put_response.status_code, 403)
        self.assertEqual(scan_response.status_code, 403)

    def test_scan_status_returns_effective_capabilities(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        UserAccess.objects.create(
            user=regular_user,
            can_edit_devices=False,
            can_edit_home_map=True,
            can_run_scans=False,
        )
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["permissions"],
            {
                "can_edit_devices": False,
                "can_edit_home_map": True,
                "can_run_scans": False,
            },
        )

    def test_users_endpoint_updates_user(self):
        user = User.objects.create_user(username="viewer", password="old-password")

        response = self.client.put(
            f"/api/v1/users/?id={user.id}",
            {
                "username": "viewer-updated",
                "first_name": "view",
                "last_name": "er",
                "password": "new-password",
                "password_confirm": "new-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "viewer-updated")
        self.assertEqual(user.first_name, "View")
        self.assertEqual(user.last_name, "Er")
        self.assertTrue(user.check_password("new-password"))

    def test_users_endpoint_deletes_user(self):
        user = User.objects.create_user(username="viewer", password="password")

        response = self.client.delete(f"/api/v1/users/?id={user.id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=user.id).exists())

    def test_users_endpoint_rejects_deleting_last_user(self):
        response = self.client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_users_endpoint_rejects_deleting_last_admin(self):
        User.objects.create_user(username="viewer", password="password")

        response = self.client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_users_endpoint_rejects_deleting_last_inactive_admin(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        User.objects.create_user(username="viewer", password="password")

        response = self.client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_users_endpoint_rejects_demoting_last_admin(self):
        response = self.client.put(
            f"/api/v1/users/?id={self.user.id}",
            {"is_staff": False},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)
