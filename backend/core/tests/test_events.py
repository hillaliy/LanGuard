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

@override_settings(NOTIFICATIONS_ENABLED=False)
class PortEventTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="Router",
            ip="192.168.1.1",
            mac="aa:bb:cc:dd:ee:ff",
            vendor="Example",
        )
        self.scan_run = ScanRun.objects.create(ip_range="192.168.1.0/24")

    def test_open_and_closed_ports_create_events(self):
        opened = sync_device_ports(
            self.device,
            [{"port": 80, "protocol": "tcp", "service": "http"}],
            scan_run=self.scan_run,
        )

        self.assertEqual(opened["ports_opened"], 1)
        self.assertEqual(opened["ports_closed"], 0)
        self.assertTrue(DevicePort.objects.get(device=self.device, port=80).open)
        self.assertTrue(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.PORT_OPENED,
                device=self.device,
                scan_run=self.scan_run,
            ).exists()
        )

        closed = sync_device_ports(self.device, [], scan_run=self.scan_run)

        self.assertEqual(closed["ports_opened"], 0)
        self.assertEqual(closed["ports_closed"], 1)
        self.assertFalse(DevicePort.objects.get(device=self.device, port=80).open)
        self.assertTrue(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.PORT_CLOSED,
                device=self.device,
                scan_run=self.scan_run,
            ).exists()
        )
