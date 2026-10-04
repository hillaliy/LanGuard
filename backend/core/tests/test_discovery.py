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

class HostnameResolutionTests(SimpleTestCase):
    def setUp(self):
        MDNS_SERVICE_HOSTNAME_CACHE["expires_at"] = 0.0
        MDNS_SERVICE_HOSTNAME_CACHE["hostnames"] = {}

    def test_clean_hostname_normalizes_dns_name(self):
        self.assertEqual(clean_hostname("living-room-device.local."), "living room device")
        self.assertEqual(clean_hostname("_IEDABF97574FD3AAD.local."), "IEDABF97574FD3AAD")

    def test_clean_hostname_returns_blank_when_unavailable(self):
        self.assertEqual(clean_hostname(""), "")

    def test_clean_hostname_rejects_dns_errors_and_numeric_values(self):
        self.assertEqual(clean_hostname("0"), "")
        self.assertEqual(clean_hostname(";; connection timed out; no servers could be reached"), "")
        self.assertEqual(clean_hostname("192.168.1.10", ip_address="192.168.1.10"), "")
        self.assertEqual(clean_hostname("_gateway"), "")
        self.assertEqual(clean_hostname("gateway.local"), "")

    @patch("core.scanning.discovery.dns_ptr_names", return_value=["deco-x60.local."])
    @patch("core.scanning.discovery.udp_exchange", return_value=b"dns response")
    def test_gateway_dns_reverse_lookup_uses_router_ptr_record(self, exchange, _ptr_names):
        self.assertEqual(
            dns_server_reverse_hostname("192.168.1.110", "192.168.1.1"),
            "deco x60",
        )
        self.assertEqual(exchange.call_args.args[1:3], ("192.168.1.1", 53))

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.ssdp_hostname", return_value="")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_service_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_returns_blank_when_reverse_dns_is_unavailable(self, *_):
        self.assertEqual(get_hostname("192.168.1.10"), "")

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.ssdp_hostname", return_value="")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_service_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="haa switch")
    @patch("core.scanning.discovery.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_uses_mdns_fallback(self, *_):
        self.assertEqual(get_hostname("192.168.1.21"), "haa switch")
        self.assertEqual(
            get_hostname("192.168.1.21", include_source=True),
            ("haa switch", Device.IdentitySource.MDNS),
        )

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.ssdp_hostname", return_value="")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_service_hostname", return_value="HAA 123456")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_uses_mdns_service_fallback(self, *_):
        self.assertEqual(get_hostname("192.168.1.42"), "HAA 123456")

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.ssdp_hostname", return_value="")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_service_hostname", return_value="living room speaker")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.socket.gethostbyaddr", return_value=("iphone.local", [], ["192.168.1.30"]))
    def test_get_hostname_keeps_direct_hostname_before_metadata_hostname(
        self,
        _reverse_dns,
        _mdns_reverse,
        mdns_service,
        llmnr,
        ssdp,
        netbios,
    ):
        self.assertEqual(get_hostname("192.168.1.30"), "iphone")
        mdns_service.assert_not_called()
        llmnr.assert_not_called()
        ssdp.assert_not_called()
        netbios.assert_not_called()

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.ssdp_hostname", return_value="")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="office pc")
    @patch("core.scanning.discovery.mdns_service_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_uses_llmnr_fallback(self, *_):
        self.assertEqual(get_hostname("192.168.1.22"), "office pc")

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.ssdp_hostname", return_value="Archer BE550")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_service_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_uses_ssdp_fallback(self, *_):
        self.assertEqual(get_hostname("192.168.1.1"), "Archer BE550")

    @patch("core.scanning.discovery.netbios_hostname", return_value="")
    @patch("core.scanning.discovery.llmnr_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.mdns_reverse_hostname", return_value="")
    @patch("core.scanning.discovery.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_uses_preloaded_network_hint(self, *_):
        self.assertEqual(
            get_hostname("192.168.1.42", hostname_hints={"192.168.1.42": "HAA 123456"}),
            "HAA 123456",
        )

    def test_preloaded_hint_preserves_discovery_source(self):
        self.assertEqual(
            get_hostname(
                "192.168.1.42",
                hostname_hints={
                    "192.168.1.42": ("HAA 123456", Device.IdentitySource.MDNS)
                },
                include_source=True,
            ),
            ("HAA 123456", Device.IdentitySource.MDNS),
        )
    def test_dns_ptr_names_returns_matching_owner(self):
        packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("21.1.168.192.in-addr.arpa")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("HAA-123456.local")).to_bytes(2, "big")
            + dns_encode_name("HAA-123456.local")
        )

        self.assertEqual(
            dns_ptr_names(packet, expected_owner="21.1.168.192.in-addr.arpa"),
            ["HAA-123456.local"],
        )

    def test_dns_ptr_names_ignores_unrelated_mdns_answer(self):
        packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("22.1.168.192.in-addr.arpa")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("Aqara-Hub.local")).to_bytes(2, "big")
            + dns_encode_name("Aqara-Hub.local")
        )

        self.assertEqual(
            dns_ptr_names(packet, expected_owner="21.1.168.192.in-addr.arpa"),
            [],
        )

    @patch("core.scanning.discovery.udp_exchange", side_effect=OSError("timeout"))
    @patch("core.scanning.discovery.mdns_legacy_responses")
    def test_mdns_reverse_hostname_checks_all_one_shot_responses(self, legacy_responses, _):
        unrelated = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("22.1.168.192.in-addr.arpa")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("Other.local")).to_bytes(2, "big")
            + dns_encode_name("Other.local")
        )
        matching = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("21.1.168.192.in-addr.arpa")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("HAA-123456.local")).to_bytes(2, "big")
            + dns_encode_name("HAA-123456.local")
        )
        legacy_responses.return_value = [
            (unrelated, "192.168.1.22"),
            (matching, "192.168.1.21"),
        ]

        self.assertEqual(mdns_reverse_hostname("192.168.1.21"), "HAA 123456")

    @patch("core.scanning.discovery.udp_exchange")
    def test_llmnr_reverse_hostname_uses_matching_ptr(self, udp_exchange):
        packet = (
            b"\x4c\x47\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("22.1.168.192.in-addr.arpa")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("Office-PC.local")).to_bytes(2, "big")
            + dns_encode_name("Office-PC.local")
        )
        udp_exchange.side_effect = [packet, OSError("timeout")]

        self.assertEqual(llmnr_reverse_hostname("192.168.1.22"), "Office PC")

    def test_hostname_from_device_description_prefers_friendly_name(self):
        body = "<root><friendlyName>Archer BE550</friendlyName><modelName>Router</modelName></root>"

        self.assertEqual(hostname_from_device_description(body, "192.168.1.1"), "Archer BE550")

    def test_mdns_service_hostnames_maps_hap_service_to_ip(self):
        packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x02\x00\x00\x00\x00"
            + dns_encode_name("HAA-123456._hap._tcp.local")
            + b"\x00\x21\x00\x01\x00\x00\x00\x78"
            + (6 + len(dns_encode_name("HAA-123456.local"))).to_bytes(2, "big")
            + (
                b"\x00\x00"
                + b"\x00\x00"
                + b"\x00\x50"
                + dns_encode_name("HAA-123456.local")
            )
            + dns_encode_name("HAA-123456.local")
            + b"\x00\x01\x00\x01\x00\x00\x00\x78\x00\x04"
            + bytes([192, 168, 1, 42])
        )

        self.assertEqual(
            mdns_service_hostnames_from_response(packet),
            {"192.168.1.42": "HAA 123456"},
        )

    def test_mdns_service_types_extracts_advertised_service(self):
        packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("_services._dns-sd._udp.local")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("_matter._tcp.local")).to_bytes(2, "big")
            + dns_encode_name("_matter._tcp.local")
        )

        self.assertEqual(mdns_service_types_from_response(packet), {"_matter._tcp.local"})

    def test_mdns_service_hostnames_correlates_records_across_packets(self):
        srv_packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("Kitchen-Sensor._matter._tcp.local")
            + b"\x00\x21\x00\x01\x00\x00\x00\x78"
            + (6 + len(dns_encode_name("sensor-123.local"))).to_bytes(2, "big")
            + b"\x00\x00\x00\x00\x00\x50"
            + dns_encode_name("sensor-123.local")
        )
        address_packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("sensor-123.local")
            + b"\x00\x01\x00\x01\x00\x00\x00\x78\x00\x04"
            + bytes([192, 168, 1, 60])
        )

        self.assertEqual(
            mdns_service_hostnames_from_responses(
                [(srv_packet, "192.168.1.60"), (address_packet, "192.168.1.60")]
            ),
            {"192.168.1.60": "Kitchen Sensor"},
        )

    @patch("core.scanning.discovery.mdns_query_responses")
    def test_mdns_service_hostname_does_not_trust_ptr_response_source_ip(self, mdns_responses):
        packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            + dns_encode_name("_printer._tcp.local")
            + b"\x00\x0c\x00\x01\x00\x00\x00\x78"
            + len(dns_encode_name("Bedroom-Printer._printer._tcp.local")).to_bytes(2, "big")
            + dns_encode_name("Bedroom-Printer._printer._tcp.local")
        )
        mdns_responses.side_effect = [[(packet, "192.168.1.42")], [], []]

        self.assertEqual(mdns_service_hostname("192.168.1.42"), "")

    @patch("core.scanning.discovery.time.sleep")
    @patch("core.scanning.discovery.mdns_query_responses")
    def test_mdns_service_hostname_retries_and_caches_service_map(self, mdns_responses, sleep):
        packet = (
            b"\x00\x00\x84\x00\x00\x00\x00\x02\x00\x00\x00\x00"
            + dns_encode_name("HAA-ABCDEF._hap._tcp.local")
            + b"\x00\x21\x00\x01\x00\x00\x00\x78"
            + (6 + len(dns_encode_name("HAA-ABCDEF.local"))).to_bytes(2, "big")
            + b"\x00\x00\x00\x00\x00\x50"
            + dns_encode_name("HAA-ABCDEF.local")
            + dns_encode_name("HAA-ABCDEF.local")
            + b"\x00\x01\x00\x01\x00\x00\x00\x78\x00\x04"
            + bytes([192, 168, 1, 55])
        )
        mdns_responses.side_effect = [[], [(packet, "192.168.1.55")], []]

        self.assertEqual(mdns_service_hostname_map(), {"192.168.1.55": "HAA ABCDEF"})
        self.assertEqual(mdns_service_hostname("192.168.1.55"), "HAA ABCDEF")
        self.assertEqual(mdns_responses.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("core.scanning.discovery.mdns_multicast_responses", side_effect=OSError("bind failed"))
    @patch("core.scanning.discovery.mdns_legacy_responses", return_value=[(b"response", "192.168.1.56")])
    def test_mdns_query_uses_one_shot_responses_when_multicast_bind_fails(
        self,
        legacy_responses,
        _multicast_responses,
    ):
        self.assertEqual(
            mdns_query_responses(["_hap._tcp.local"]),
            [(b"response", "192.168.1.56")],
        )
        legacy_responses.assert_called_once()

    @patch("core.scanning.discovery.requests.get")
    def test_ssdp_hostname_from_response_fetches_device_description(self, get):
        get.return_value.text = "<root><friendlyName>Archer BE550</friendlyName></root>"
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"LOCATION: http://192.168.1.1:80/rootDesc.xml\r\n"
            b"\r\n"
        )

        self.assertEqual(ssdp_hostname_from_response(response, "192.168.1.1"), "Archer BE550")

    @patch("core.scanning.discovery.requests.get")
    def test_ssdp_metadata_reads_vendor_and_model_from_device_description(self, get):
        get.return_value.text = (
            "<root><manufacturer>TP-Link Systems Inc.</manufacturer>"
            "<modelName>Deco X60</modelName></root>"
        )
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"LOCATION: http://192.168.1.1:80/rootDesc.xml\r\n\r\n"
        )

        self.assertEqual(
            ssdp_metadata_from_response(response, "192.168.1.1"),
            {"vendor": "TP-Link Systems Inc.", "hostname": "Deco X60"},
        )

    @patch("core.scanning.discovery.requests.get")
    def test_ssdp_hostname_from_response_ignores_other_device_location(self, get):
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"LOCATION: http://192.168.1.99:80/rootDesc.xml\r\n"
            b"\r\n"
        )

        self.assertEqual(ssdp_hostname_from_response(response, "192.168.1.1"), "")
        get.assert_not_called()

    def test_web_interface_candidates_use_only_open_web_ports(self):
        self.assertEqual(
            web_interface_candidates("192.168.1.20", [22, 80, 8443]),
            ["http://192.168.1.20", "https://192.168.1.20:8443"],
        )
        self.assertEqual(web_interface_candidates("8.8.8.8", [80, 443]), [])

    @patch("core.scanning.discovery.requests.get")
    def test_detect_web_interface_tries_candidates_until_one_responds(self, get):
        response = Mock()
        get.side_effect = [requests.ConnectionError("closed"), response]

        detected = detect_web_interface("192.168.1.20", [80, 443])

        self.assertEqual(detected, "http://192.168.1.20")
        self.assertEqual(get.call_count, 2)
        response.close.assert_called_once()

    def test_manuf_parser_preserves_original_vendor_name(self):
        entry = ManufVendorDB.parse_line(
            "70:B3:D5:0D:00:00/36 ProHound ProHound Controles Eirelli"
        )

        self.assertEqual(entry, (0x70B3D50D0, 36, "ProHound Controles Eirelli"))

    @patch("core.scanning.vendor.ManufVendorDB.entries", return_value=[
        (0x70B3D5, 24, "Generic 24-bit Vendor"),
        (0x70B3D50D0, 36, "Specific 36-bit Vendor"),
    ])
    def test_manuf_vendor_prefers_more_specific_prefix(self, _):
        self.assertEqual(manuf_vendor("70:b3:d5:0d:04:01"), "Specific 36-bit Vendor")

    def test_manuf_vendor_uses_bundled_database(self):
        self.assertEqual(
            manuf_vendor("bc:5e:33:b0:02:04"),
            "Hangzhou Hikvision Digital Technology Co.,Ltd.",
        )

    def test_manuf_vendor_recognizes_current_tp_link_prefix(self):
        self.assertEqual(manuf_vendor("3c:6a:d2:f4:07:74"), "TP-Link Systems Inc.")

    def test_preferred_vendor_rejects_mac_address_fallback(self):
        self.assertEqual(preferred_vendor("3c:6a:d2:f4:07:74"), "")

    def test_manuf_vendor_ignores_locally_administered_mac(self):
        self.assertEqual(manuf_vendor("f6:34:f0:00:c6:8d"), "")
