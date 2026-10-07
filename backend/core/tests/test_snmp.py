from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from scapy.asn1.asn1 import ASN1_INTEGER, ASN1_OID, ASN1_STRING
from scapy.layers.snmp import SNMP, SNMPresponse, SNMPvarbind

from ..models import Device, ScanRun
from ..scanning.reconciliation import sync_discovered_device
from ..scanning.snmp import (
    HOST_PRINTER_DEVICE_TYPE,
    SYSTEM_OIDS,
    classify_snmp_device,
    discover_snmp_inventory,
    interface_inventory,
    lldp_neighbors,
    snmp_exchange,
    snmp_get,
    snmp_value,
)


class SnmpInventoryTests(TestCase):
    def test_binary_identifier_is_only_formatted_as_mac_when_six_bytes(self):
        self.assertEqual(snmp_value(ASN1_STRING(b"switch-01"), mac=True), "switch-01")
        self.assertEqual(
            snmp_value(ASN1_STRING(bytes.fromhex("001122334455")), mac=True),
            "00:11:22:33:44:55",
        )

    @patch("core.scanning.snmp.random.randint", return_value=123)
    @patch("core.scanning.snmp.socket.socket")
    def test_exchange_parses_matching_v2c_response(self, socket_factory, _):
        response = SNMP(
            version=1,
            community="readonly",
            PDU=SNMPresponse(
                id=123,
                varbindlist=[
                    SNMPvarbind(
                        oid=SYSTEM_OIDS["name"],
                        value=ASN1_STRING(b"office-switch"),
                    )
                ],
            ),
        )
        sock = MagicMock()
        sock.recvfrom.return_value = (bytes(response), ("192.168.1.2", 161))
        socket_factory.return_value.__enter__.return_value = sock

        result = snmp_exchange(
            "192.168.1.2",
            "readonly",
            [SYSTEM_OIDS["name"]],
        )

        self.assertEqual(result[0][0], SYSTEM_OIDS["name"])
        self.assertEqual(result[0][1].val, b"office-switch")
        sock.settimeout.assert_called_once_with(0.4)
        sock.sendto.assert_called_once()

    @patch("core.scanning.snmp.snmp_exchange")
    def test_system_get_decodes_strings_integers_and_object_ids(self, exchange):
        exchange.return_value = [
            (SYSTEM_OIDS["description"], ASN1_STRING(b"Cisco managed switch")),
            (SYSTEM_OIDS["object_id"], ASN1_OID("1.3.6.1.4.1.9.1.1")),
            (SYSTEM_OIDS["uptime_ticks"], ASN1_INTEGER(12345)),
        ]

        values = snmp_get(
            "192.168.1.2",
            "readonly",
            {
                "description": SYSTEM_OIDS["description"],
                "object_id": SYSTEM_OIDS["object_id"],
                "uptime_ticks": SYSTEM_OIDS["uptime_ticks"],
            },
        )

        self.assertEqual(values["description"], "Cisco managed switch")
        self.assertEqual(values["object_id"], "1.3.6.1.4.1.9.1.1")
        self.assertEqual(values["uptime_ticks"], 12345)

    def test_interface_inventory_combines_columns_by_index(self):
        interfaces = interface_inventory(
            {
                "name": {"1": "Gi0/1"},
                "description": {"1": "Uplink"},
                "type": {"1": 6},
                "speed_bps": {"1": 1_000_000_000},
                "high_speed_mbps": {"1": 1000},
                "mac": {"1": "00:11:22:33:44:55"},
                "admin_status": {"1": 1},
                "oper_status": {"1": 2},
            }
        )

        self.assertEqual(
            interfaces,
            [
                {
                    "index": 1,
                    "name": "Gi0/1",
                    "description": "Uplink",
                    "type": "Ethernet",
                    "speed_mbps": 1000,
                    "mac": "00:11:22:33:44:55",
                    "admin_status": "up",
                    "oper_status": "down",
                }
            ],
        )

    def test_lldp_neighbors_link_remote_entry_to_local_port(self):
        neighbors = lldp_neighbors(
            {
                "port_id": {"7": "Gi0/7"},
                "description": {"7": "Office AP"},
            },
            {
                "chassis_id": {"120.7.1": "aa:bb:cc:dd:ee:ff"},
                "port_id": {"120.7.1": "eth0"},
                "system_name": {"120.7.1": "office-ap"},
                "system_description": {"120.7.1": "Wireless access point"},
            },
        )

        self.assertEqual(neighbors[0]["local_port"], "Gi0/7")
        self.assertEqual(neighbors[0]["system_name"], "office-ap")

    def test_device_classification_uses_printer_mib_and_lldp(self):
        self.assertEqual(
            classify_snmp_device({}, [], {HOST_PRINTER_DEVICE_TYPE}),
            "printer",
        )
        self.assertEqual(
            classify_snmp_device({"description": "Managed device"}, [{}], set()),
            "switch",
        )

    @patch("core.scanning.snmp.collect_snmp_inventory")
    def test_discovery_is_limited_to_private_ipv4_targets(self, collect):
        collect.side_effect = lambda ip, *_args, **_kwargs: {
            "device_type": "managed_device",
            "system": {"name": ip},
            "interfaces": [],
            "neighbors": [],
        }

        inventory = discover_snmp_inventory(
            ["192.168.1.3", "192.168.1.2", "fd00::1", "8.8.8.8", "invalid"],
            "readonly",
            max_devices=1,
            concurrency=1,
        )

        self.assertEqual(list(inventory), ["192.168.1.2"])
        collect.assert_called_once()

    @patch("core.scanning.snmp.collect_snmp_inventory")
    def test_discovery_can_be_disabled_with_zero_device_limit(self, collect):
        self.assertEqual(
            discover_snmp_inventory(["192.168.1.2"], "readonly", max_devices=0),
            {},
        )
        collect.assert_not_called()

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value=("", ""))
    def test_reconciliation_persists_snmp_inventory_and_infers_role(self, _):
        observed_at = timezone.now()
        scan_run = ScanRun.objects.create(ip_range="192.168.1.0/24")
        metadata = {
            "device_type": "switch",
            "vendor": "Cisco",
            "system": {"name": "office-switch"},
            "interfaces": [{"index": 1, "name": "Gi0/1"}],
            "neighbors": [],
        }

        sync_discovered_device(
            (None, SimpleNamespace(psrc="192.168.1.2", hwsrc="00:11:22:33:44:55")),
            scan_run=scan_run,
            scan_started_at=observed_at,
            snmp_hints={"192.168.1.2": metadata},
        )

        device = Device.objects.get(mac="00:11:22:33:44:55")
        self.assertEqual(device.snmp_data, metadata)
        self.assertEqual(device.snmp_last_seen, observed_at)
        self.assertEqual(device.role, "switch")
        self.assertEqual(device.icon, "router")
