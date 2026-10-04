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

class DeviceAttentionApiTests(TestCase):
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

    def test_bulk_attention_review_is_invalidated_by_port_change(self):
        self.device.known = True
        self.device.vendor = "Linux"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=3389, protocol="tcp", open=True)
        response = self.client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id], "acknowledge_attention": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        DevicePort.objects.create(device=self.device, port=5900, protocol="tcp", open=True)

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]
        self.assertFalse(device["attention_acknowledged"])
        self.assertTrue(device["needs_attention"])

    def test_device_endpoint_filters_needs_attention_before_pagination(self):
        now = timezone.now()
        self.device.known = True
        self.device.vendor = "Laptop vendor"
        self.device.save(update_fields=["known", "vendor"])
        unknown_device = Device.objects.create(
            name="Unknown device",
            ip="192.168.1.31",
            mac="bb:bb:bb:bb:bb:31",
        )
        risky_device = Device.objects.create(
            name="Risky device",
            ip="192.168.1.32",
            mac="bb:bb:bb:bb:bb:32",
            known=True,
            vendor="Linux",
        )
        DevicePort.objects.create(
            device=risky_device,
            port=3389,
            protocol="tcp",
            open=True,
        )
        offline_device = Device.objects.create(
            name="Long offline device",
            ip="192.168.1.33",
            mac="bb:bb:bb:bb:bb:33",
            known=True,
            vendor="Example vendor",
            online=False,
            status=Device.Status.OFFLINE,
            lastseen=now - timedelta(days=8),
        )
        conflict_device = Device.objects.create(
            name="Identity conflict device",
            ip="192.168.1.34",
            mac="bb:bb:bb:bb:bb:34",
            known=True,
            vendor="Example vendor",
            identity_conflict_reason=(
                "IP 192.168.1.34 was reported by multiple MAC addresses"
            ),
            identity_conflict_detected_at=now,
        )
        reviewed_device = Device.objects.create(
            name="Reviewed device",
            ip="192.168.1.35",
            mac="bb:bb:bb:bb:bb:35",
            known=True,
            vendor="Linux",
        )
        DevicePort.objects.create(
            device=reviewed_device,
            port=5900,
            protocol="tcp",
            open=True,
        )
        review_response = self.client.put(
            f"/api/v1/device/?id={reviewed_device.id}",
            {"acknowledge_attention": True},
            format="json",
        )
        self.assertEqual(review_response.status_code, 202)

        first_page = self.client.get(
            "/api/v1/device/",
            {
                "needs_attention": "true",
                "ordering": "name",
                "limit": 2,
                "offset": 0,
            },
        )
        second_page = self.client.get(
            "/api/v1/device/",
            {
                "needs_attention": "true",
                "ordering": "name",
                "limit": 2,
                "offset": 2,
            },
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(first_page.data["pagination"]["count"], 4)
        self.assertEqual(first_page.data["pagination"]["next_offset"], 2)
        self.assertIsNone(second_page.data["pagination"]["next_offset"])
        returned_ids = {
            device["id"]
            for device in first_page.data["data"] + second_page.data["data"]
        }
        self.assertEqual(
            returned_ids,
            {
                unknown_device.id,
                risky_device.id,
                offline_device.id,
                conflict_device.id,
            },
        )
        self.assertNotIn(reviewed_device.id, returned_ids)
        self.assertNotIn(self.device.id, returned_ids)

    def test_device_endpoint_includes_low_risk_badge_data(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.save()

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "low")
        self.assertEqual(device["risk_score"], 0)
        self.assertEqual(device["risk_reasons"], [])
        self.assertEqual(device["attention_reasons"], [])

    def test_known_device_missing_vendor_and_recent_scan_stays_low_risk(self):
        self.device.known = True
        self.device.vendor = ""
        self.device.status = Device.Status.RECENTLY_SEEN
        self.device.missed_scans = 1
        self.device.save(
            update_fields=["known", "vendor", "status", "missed_scans"]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["risk_level"], "low")
        self.assertEqual(device["risk_score"], 0)
        self.assertEqual(device["risk_reasons"], [])
        self.assertEqual(device["attention_reasons"], [])
        self.assertFalse(device["needs_attention"])

    def test_unknown_device_keeps_missing_vendor_and_recent_scan_risk(self):
        self.device.vendor = ""
        self.device.status = Device.Status.RECENTLY_SEEN
        self.device.missed_scans = 1
        self.device.save(update_fields=["vendor", "status", "missed_scans"])

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["risk_level"], "high")
        self.assertIn("No vendor detected", device["risk_reasons"])
        self.assertIn("Recently missed scans", device["risk_reasons"])
        self.assertTrue(device["needs_attention"])

    def test_device_endpoint_explains_recent_ip_mac_conflict(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.identity_conflict_reason = (
            "IP 192.168.1.20 was reported by multiple MAC addresses: "
            "aa:bb:cc:dd:ee:ff, bb:bb:bb:bb:bb:bb"
        )
        self.device.identity_conflict_detected_at = timezone.now()
        self.device.save(
            update_fields=[
                "known",
                "vendor",
                "identity_conflict_reason",
                "identity_conflict_detected_at",
            ]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(
            device["attention_reasons"],
            [self.device.identity_conflict_reason],
        )
        self.assertTrue(device["needs_attention"])

    def test_expired_ip_mac_conflict_does_not_need_attention(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.identity_conflict_reason = (
            "IP 192.168.1.20 was reported by multiple MAC addresses"
        )
        self.device.identity_conflict_detected_at = timezone.now() - timedelta(days=8)
        self.device.save(
            update_fields=[
                "known",
                "vendor",
                "identity_conflict_reason",
                "identity_conflict_detected_at",
            ]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["attention_reasons"], [])
        self.assertFalse(device["needs_attention"])

    def test_device_endpoint_flags_unknown_device_with_risky_ports(self):
        self.device.known = False
        self.device.vendor = ""
        self.device.save()
        DevicePort.objects.create(device=self.device, port=22, protocol="tcp", open=True)
        DevicePort.objects.create(device=self.device, port=445, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "high")
        self.assertGreaterEqual(device["risk_score"], 5)
        self.assertIn("New unknown device", device["risk_reasons"])
        self.assertTrue(
            any("Risky open ports" in reason for reason in device["risk_reasons"])
        )

    def test_device_endpoint_keeps_known_camera_with_expected_ports_low_risk(self):
        self.device.known = True
        self.device.role = "camera"
        self.device.vendor = "Hikvision"
        self.device.save()
        for port in [80, 443, 554, 8443]:
            DevicePort.objects.create(device=self.device, port=port, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "low")
        self.assertNotIn("Many open ports", device["risk_reasons"])

    def test_device_endpoint_keeps_known_server_with_expected_ports_low_risk(self):
        self.device.known = True
        self.device.role = "server"
        self.device.vendor = "Linux"
        self.device.save()
        for port in [22, 80, 443, 8080, 8443]:
            DevicePort.objects.create(device=self.device, port=port, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "low")
        self.assertNotIn("Many open ports", device["risk_reasons"])

    def test_device_endpoint_still_flags_known_server_with_dangerous_remote_port(self):
        self.device.known = True
        self.device.role = "server"
        self.device.vendor = "Linux"
        self.device.save()
        DevicePort.objects.create(device=self.device, port=3389, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "medium")
        self.assertTrue(
            any("Risky open ports" in reason for reason in device["risk_reasons"])
        )
        self.assertTrue(
            any("Risky open ports" in reason for reason in device["attention_reasons"])
        )

    def test_known_device_can_acknowledge_current_risk_and_save_comments(self):
        self.device.known = True
        self.device.vendor = "Linux"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=3389, protocol="tcp", open=True)

        before = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertTrue(before["needs_attention"])
        self.assertFalse(before["attention_acknowledged"])

        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {
                "comments": "Remote desktop is intentionally exposed on the LAN.",
                "acknowledge_attention": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        after = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertEqual(
            after["comments"],
            "Remote desktop is intentionally exposed on the LAN.",
        )
        self.assertTrue(after["attention_acknowledged"])
        self.assertFalse(after["needs_attention"])
        self.assertNotIn("attention_acknowledged_signature", after)

    def test_risk_change_invalidates_attention_acknowledgement(self):
        self.device.known = True
        self.device.vendor = "Linux"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=3389, protocol="tcp", open=True)
        self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"acknowledge_attention": True},
            format="json",
        )

        DevicePort.objects.create(device=self.device, port=5900, protocol="tcp", open=True)

        device = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertFalse(device["attention_acknowledged"])
        self.assertTrue(device["needs_attention"])

    def test_long_offline_period_invalidates_attention_acknowledgement(self):
        self.device.known = True
        self.device.vendor = "Linux"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=3389, protocol="tcp", open=True)
        self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"acknowledge_attention": True},
            format="json",
        )

        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.lastseen = timezone.now() - timedelta(days=8)
        self.device.save(update_fields=["online", "status", "lastseen"])

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]
        self.assertIn("Offline for over 7 days", device["attention_reasons"])
        self.assertFalse(device["attention_acknowledged"])
        self.assertTrue(device["needs_attention"])

    def test_port_change_invalidates_acknowledgement_when_risk_level_is_unchanged(self):
        self.device.known = True
        self.device.vendor = "Example vendor"
        self.device.save(update_fields=["known", "vendor"])
        for port in [1000, 1001, 1002, 1003]:
            DevicePort.objects.create(device=self.device, port=port, protocol="tcp", open=True)
        self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"acknowledge_attention": True},
            format="json",
        )

        self.device.ports.get(port=1003).delete()
        DevicePort.objects.create(device=self.device, port=1004, protocol="tcp", open=True)

        device = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertEqual(device["risk_level"], "medium")
        self.assertFalse(device["attention_acknowledged"])
        self.assertTrue(device["needs_attention"])

    def test_unknown_device_cannot_acknowledge_attention(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"acknowledge_attention": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("acknowledge_attention", response.data["info"])
