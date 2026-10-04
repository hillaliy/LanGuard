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

class PortGuidanceCatalogTests(SimpleTestCase):
    def test_catalog_covers_initial_guidance_ports(self):
        required_ports = {
            21,
            53,
            80,
            135,
            139,
            443,
            445,
            515,
            548,
            554,
            631,
            873,
            1883,
            2049,
            3389,
            5000,
            5001,
            5555,
            5900,
            8080,
            8123,
            8443,
            8883,
            9100,
        }

        self.assertTrue(
            required_ports.issubset(
                {port for protocol, port in PORT_CATALOG if protocol == "tcp"}
            )
        )

    def test_known_printer_gets_expected_printing_guidance(self):
        device = SimpleNamespace(known=True, role="printer", icon="printer")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 9100, "service": "jetdirect"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "RAW printing")

    def test_known_nas_gets_expected_file_sharing_guidance(self):
        device = SimpleNamespace(known=True, role="nas", icon="nas")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 445, "service": "microsoft-ds"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "SMB")

    def test_known_gateway_gets_expected_dns_guidance(self):
        device = SimpleNamespace(known=True, role="gateway", icon="router")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 53, "service": "domain"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "DNS")

    def test_netbios_guidance_recommends_disabling_legacy_service(self):
        device = SimpleNamespace(known=True, role="computer", icon="desktop")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 139, "service": "netbios-ssn"},
        )

        self.assertEqual(guidance["recommendation"], "usually_disable")
        self.assertEqual(guidance["service_name"], "NetBIOS Session Service")

    def test_android_debug_bridge_guidance_recommends_disabling_service(self):
        device = SimpleNamespace(known=True, role="streamer", icon="tv")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 5555, "service": "freeciv"},
        )

        self.assertEqual(guidance["recommendation"], "usually_disable")
        self.assertEqual(guidance["service_name"], "Android Debug Bridge")

    def test_known_home_automation_hub_gets_expected_mqtt_guidance(self):
        device = SimpleNamespace(known=True, role="hub", icon="smart-hub")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 1883, "service": "mqtt"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "MQTT")

    def test_unknown_catalog_port_gets_generic_non_definitive_guidance(self):
        device = SimpleNamespace(known=True, role="device", icon="unknown")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 12345, "service": ""},
        )

        self.assertEqual(guidance["recommendation"], "review")
        self.assertEqual(guidance["service_name"], "Unidentified service")
        self.assertIn("not enough", guidance["context"])
