from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from ..models import (
    AppSettings,
    Device,
    DeviceIPAddressAssignment,
    DevicePort,
    NetworkEvent,
    ScanRun,
)
from ..serializers.devices import device_attention_reasons
from ..scanning.identity import (
    guess_device_identity,
    mismatched_default_haa_hostname,
    preferred_vendor,
)
from ..scanning.network import (
    default_gateway_from_proc_route,
    discover_devices,
    local_scanner_interface,
)
from ..scanning.orchestration import scan
from ..scanning.presence import (
    clear_stale_gateways,
    mark_missing_devices_offline,
)
from ..scanning.ranges import validate_ip_ranges
from ..scanning.reconciliation import sync_discovered_device

@override_settings(NOTIFICATIONS_ENABLED=False)
class ScanStabilityTests(TestCase):
    def scan_element(self, ip, mac):
        return (None, SimpleNamespace(psrc=ip, hwsrc=mac))

    def create_ip_mac_conflict(self, observed_at):
        original = Device.objects.create(
            name="Entry light",
            ip="192.168.1.3",
            mac="d8:f1:5b:82:63:53",
            known=True,
            lastseen=observed_at - timedelta(minutes=5),
        )
        sync_discovered_device(
            self.scan_element("192.168.1.3", "00:55:7b:b5:7d:f7"),
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
            scan_started_at=observed_at,
        )
        return original, Device.objects.get(mac="00:55:7b:b5:7d:f7")

    def test_default_haa_hostname_must_match_observed_mac(self):
        self.assertFalse(
            mismatched_default_haa_hostname(
                "HAA 826353",
                "d8:f1:5b:82:63:53",
            )
        )
        self.assertTrue(
            mismatched_default_haa_hostname(
                "HAA 826353",
                "00:55:7b:b5:7d:f7",
            )
        )
        self.assertFalse(
            mismatched_default_haa_hostname(
                "HAA living-room-switch",
                "00:55:7b:b5:7d:f7",
            )
        )

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch(
        "core.scanning.reconciliation.get_hostname",
        return_value=("HAA 826353", Device.IdentitySource.MDNS),
    )
    def test_mismatched_haa_hostname_is_silently_ignored(self, _):
        sync_discovered_device(
            self.scan_element("192.168.1.3", "00:55:7b:b5:7d:f7"),
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device = Device.objects.get(mac="00:55:7b:b5:7d:f7")
        self.assertEqual(device.hostname, "")
        self.assertEqual(device.hostname_source, "")
        self.assertEqual(device.identity_conflict_reason, "")
        self.assertIsNone(device.identity_conflict_detected_at)

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch(
        "core.scanning.reconciliation.get_hostname",
        return_value=("HAA 826353", Device.IdentitySource.MDNS),
    )
    def test_recent_ip_mac_conflict_blocks_ip_identity_and_marks_both_devices(
        self,
        get_hostname,
    ):
        observed_at = timezone.now()
        original = Device.objects.create(
            name="Entry light",
            hostname="HAA 826353",
            hostname_source=Device.IdentitySource.MDNS,
            ip="192.168.1.3",
            mac="d8:f1:5b:82:63:53",
            known=True,
            lastseen=observed_at - timedelta(minutes=5),
        )

        sync_discovered_device(
            self.scan_element("192.168.1.3", "00:55:7b:b5:7d:f7"),
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
            scan_started_at=observed_at,
            hostname_hints={
                "192.168.1.3": ("HAA 826353", Device.IdentitySource.MDNS),
            },
        )

        original.refresh_from_db()
        duplicate = Device.objects.get(mac="00:55:7b:b5:7d:f7")
        self.assertEqual(duplicate.hostname, "")
        self.assertEqual(duplicate.hostname_source, "")
        self.assertIn("192.168.1.3", duplicate.identity_conflict_reason)
        self.assertIn(original.mac, duplicate.identity_conflict_reason)
        self.assertEqual(
            original.identity_conflict_reason,
            duplicate.identity_conflict_reason,
        )
        self.assertEqual(original.identity_conflict_detected_at, observed_at)
        self.assertEqual(
            DeviceIPAddressAssignment.objects.filter(
                ip="192.168.1.3",
                valid_until__isnull=True,
            ).count(),
            2,
        )
        get_hostname.assert_not_called()

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value=("", ""))
    def test_ip_mac_conflict_remains_while_recent_conflict_is_still_detected(self, _):
        observed_at = timezone.now()
        original, duplicate = self.create_ip_mac_conflict(observed_at)
        conflict_reason = duplicate.identity_conflict_reason

        sync_discovered_device(
            self.scan_element(duplicate.ip, duplicate.mac),
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
            scan_started_at=observed_at + timedelta(minutes=30),
        )

        original.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertEqual(original.identity_conflict_reason, conflict_reason)
        self.assertEqual(duplicate.identity_conflict_reason, conflict_reason)

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value=("", ""))
    def test_resolved_ip_mac_conflict_is_cleared_for_all_affected_devices(self, _):
        observed_at = timezone.now()
        original, duplicate = self.create_ip_mac_conflict(observed_at)

        sync_discovered_device(
            self.scan_element(duplicate.ip, duplicate.mac),
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
            scan_started_at=observed_at + timedelta(hours=2),
        )

        original.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertEqual(original.identity_conflict_reason, "")
        self.assertIsNone(original.identity_conflict_detected_at)
        self.assertEqual(duplicate.identity_conflict_reason, "")
        self.assertIsNone(duplicate.identity_conflict_detected_at)
        active_assignment = DeviceIPAddressAssignment.objects.get(
            ip=duplicate.ip,
            valid_until__isnull=True,
        )
        self.assertEqual(active_assignment.device, duplicate)

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value=("", ""))
    def test_resolved_ip_mac_conflict_returns_when_detected_again(self, _):
        observed_at = timezone.now()
        original, duplicate = self.create_ip_mac_conflict(observed_at)
        resolved_at = observed_at + timedelta(hours=2)
        sync_discovered_device(
            self.scan_element(duplicate.ip, duplicate.mac),
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
            scan_started_at=resolved_at,
        )

        sync_discovered_device(
            self.scan_element(original.ip, original.mac),
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
            scan_started_at=resolved_at + timedelta(minutes=5),
        )

        original.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertIn("was reported by multiple MAC addresses", original.identity_conflict_reason)
        self.assertEqual(original.identity_conflict_reason, duplicate.identity_conflict_reason)

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value=("", ""))
    def test_resolving_ip_mac_conflict_keeps_other_attention_reasons(self, _):
        observed_at = timezone.now()
        _, duplicate = self.create_ip_mac_conflict(observed_at)
        duplicate.known = True
        duplicate.save(update_fields=["known"])
        DevicePort.objects.create(device=duplicate, port=3389, protocol="tcp", open=True)

        sync_discovered_device(
            self.scan_element(duplicate.ip, duplicate.mac),
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
            scan_started_at=observed_at + timedelta(hours=2),
        )

        duplicate.refresh_from_db()
        reasons = device_attention_reasons(duplicate)
        self.assertFalse(any("multiple MAC addresses" in reason for reason in reasons))
        self.assertTrue(any("Remote Desktop" in reason for reason in reasons))

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch(
        "core.scanning.reconciliation.get_hostname",
        return_value=("Office printer", Device.IdentitySource.MDNS),
    )
    def test_stale_device_with_reused_ip_does_not_trigger_conflict(self, _):
        old_device = Device.objects.create(
            name="Old device",
            ip="192.168.1.30",
            mac="aa:bb:cc:dd:ee:01",
            lastseen=timezone.now() - timedelta(hours=2),
        )
        observed_at = timezone.now()

        sync_discovered_device(
            self.scan_element("192.168.1.30", "aa:bb:cc:dd:ee:02"),
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
            scan_started_at=observed_at,
        )

        device = Device.objects.get(mac="aa:bb:cc:dd:ee:02")
        self.assertEqual(device.hostname, "Office printer")
        self.assertEqual(device.identity_conflict_reason, "")
        self.assertEqual(
            DeviceIPAddressAssignment.objects.get(
                device=old_device,
                ip="192.168.1.30",
            ).valid_until,
            DeviceIPAddressAssignment.objects.get(
                device=device,
                ip="192.168.1.30",
            ).valid_from,
        )

    @override_settings(PORT_SCAN_ENABLED=False)
    def test_existing_device_ip_change_creates_history_event(self):
        device = Device.objects.create(
            name="Camera",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:ff",
            known=True,
        )
        scan_run = ScanRun.objects.create(ip_range="192.168.1.0/24")
        observed_at = timezone.now()

        sync_discovered_device(
            self.scan_element("192.168.1.25", device.mac),
            scan_run=scan_run,
            scan_started_at=observed_at,
        )

        device.refresh_from_db()
        self.assertEqual(device.ip, "192.168.1.25")
        event = NetworkEvent.objects.get(
            device=device,
            scan_run=scan_run,
            event_type=NetworkEvent.EventType.IP_CHANGED,
        )
        self.assertEqual(
            event.message,
            "Camera changed IP from 192.168.1.10 to 192.168.1.25",
        )
        self.assertEqual(
            event.metadata,
            {
                "old_ip": "192.168.1.10",
                "new_ip": "192.168.1.25",
                "notification_skipped": "known_device",
            },
        )
        old_assignment = DeviceIPAddressAssignment.objects.get(
            device=device,
            ip="192.168.1.10",
        )
        current_assignment = DeviceIPAddressAssignment.objects.get(
            device=device,
            ip="192.168.1.25",
        )
        self.assertEqual(old_assignment.valid_until, observed_at)
        self.assertEqual(current_assignment.valid_from, observed_at)
        self.assertIsNone(current_assignment.valid_until)

    @override_settings(PORT_SCAN_ENABLED=False)
    def test_unchanged_device_ip_does_not_create_history_event(self):
        device = Device.objects.create(
            name="Camera",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:ff",
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        self.assertFalse(
            NetworkEvent.objects.filter(
                device=device,
                event_type=NetworkEvent.EventType.IP_CHANGED,
            ).exists()
        )

    @override_settings(SCAN_ARP_RETRIES=2, SCAN_ARP_TIMEOUT=2)
    @patch("core.scanning.network.scapy.conf.route.route", return_value=("eth0", "192.168.1.20", "0.0.0.0"))
    @patch("core.scanning.network.scapy.srp")
    def test_discover_devices_retries_and_deduplicates_by_mac(self, srp, route):
        first = self.scan_element("192.168.1.10", "AA:BB:CC:DD:EE:01")
        second = self.scan_element("192.168.1.11", "AA:BB:CC:DD:EE:02")
        duplicate = self.scan_element("192.168.1.10", "aa:bb:cc:dd:ee:01")
        srp.side_effect = [([first], None), ([duplicate, second], None)]

        devices = discover_devices("192.168.1.0/24")

        self.assertEqual(len(devices), 2)
        self.assertEqual(srp.call_count, 2)
        route.assert_called_once_with("192.168.1.1")
        self.assertEqual(srp.call_args.kwargs["iface"], "eth0")

    @override_settings(SCAN_ARP_RETRIES=1, SCAN_ARP_TIMEOUT=2)
    @patch("core.scanning.network.scapy.conf.route.route")
    @patch("core.scanning.network.scapy.srp")
    def test_discover_devices_uses_route_interface_for_each_network(self, srp, route):
        first = self.scan_element("192.168.1.10", "aa:bb:cc:dd:ee:01")
        second = self.scan_element("192.168.20.10", "aa:bb:cc:dd:ee:02")
        route.side_effect = [
            ("eth0", "192.168.1.20", "0.0.0.0"),
            ("eth0.20", "192.168.20.20", "0.0.0.0"),
        ]
        srp.side_effect = [([first], None), ([second], None)]

        discover_devices("192.168.1.0/24")
        discover_devices("192.168.20.0/24")

        self.assertEqual(
            [call.args[0] for call in route.call_args_list],
            ["192.168.1.1", "192.168.20.1"],
        )
        self.assertEqual(
            [call.kwargs["iface"] for call in srp.call_args_list],
            ["eth0", "eth0.20"],
        )

    @patch("core.scanning.network.scapy.get_if_hwaddr", return_value="AA:BB:CC:DD:EE:FF")
    @patch("core.scanning.network.scapy.conf.route.route")
    def test_local_scanner_interface_uses_route_for_scanned_network(self, route, _):
        route.return_value = ("eth0", "192.168.1.20", "192.168.1.1")

        interface = local_scanner_interface(
            "192.168.1.0/24",
            route_target="192.168.1.1",
        )

        route.assert_called_once_with("192.168.1.1")
        self.assertEqual(
            interface,
            {"ip": "192.168.1.20", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @patch("core.scanning.network.scapy.get_if_hwaddr", return_value="AA:BB:CC:DD:EE:FF")
    @patch("core.scanning.network.scapy.conf.route.route")
    def test_local_scanner_interface_ignores_source_outside_scan_range(self, route, _):
        route.return_value = ("eth0", "10.0.0.20", "10.0.0.1")

        self.assertIsNone(local_scanner_interface("192.168.1.0/24"))

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value="server")
    def test_local_scanner_updates_imported_device_without_duplicate(self, _):
        device = Device.objects.create(
            name="Server",
            ip="192.168.1.20",
            mac="aa:bb:cc:dd:ee:ff",
            online=False,
            status=Device.Status.OFFLINE,
            status_source=Device.StatusSource.NONE,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
            status_source=Device.StatusSource.LOCAL,
        )

        device.refresh_from_db()
        self.assertEqual(Device.objects.count(), 1)
        self.assertTrue(device.online)
        self.assertEqual(device.status_source, Device.StatusSource.LOCAL)
        self.assertEqual(
            device.status_reason,
            "Detected on the local scanner interface",
        )

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.orchestration.mark_missing_devices_offline")
    @patch("core.scanning.orchestration.clear_stale_gateways")
    @patch("core.scanning.orchestration.sync_discovered_device")
    @patch("core.scanning.orchestration.ssdp_metadata_map", return_value={})
    @patch("core.scanning.orchestration.discover_hostname_hints", return_value={})
    @patch("core.scanning.orchestration.local_scanner_interface")
    @patch("core.scanning.orchestration.discover_devices")
    @patch("core.scanning.orchestration.get_default_gateway_ip", return_value="192.168.1.1")
    def test_scan_includes_local_interface_as_online_device(
        self,
        _,
        discover,
        local_interface,
        __,
        ___,
        sync_device,
        clear_gateways,
        mark_missing,
    ):
        remote = self.scan_element("192.168.1.10", "aa:bb:cc:dd:ee:10")
        discover.return_value = [remote]
        local_interface.return_value = {
            "ip": "192.168.1.20",
            "mac": "aa:bb:cc:dd:ee:20",
        }
        sync_device.return_value = {
            "new_devices": 0,
            "ports_opened": 0,
            "ports_closed": 0,
        }

        scan_run = scan("192.168.1.0/24")

        self.assertEqual(sync_device.call_count, 2)
        self.assertEqual(
            sync_device.call_args_list[0].kwargs["status_source"],
            Device.StatusSource.ARP,
        )
        self.assertEqual(
            sync_device.call_args_list[1].kwargs["status_source"],
            Device.StatusSource.LOCAL,
        )
        mark_missing.assert_called_once_with(
            ["aa:bb:cc:dd:ee:10", "aa:bb:cc:dd:ee:20"],
            scan_run=scan_run,
            ip_ranges=["192.168.1.0/24"],
        )
        clear_gateways.assert_called_once_with("192.168.1.1")
        self.assertEqual(scan_run.devices_seen, 2)

    @override_settings(PORT_SCAN_ENABLED=False)
    def test_scan_combines_multiple_network_ranges(self):
        first = self.scan_element("192.168.1.10", "aa:bb:cc:dd:ee:10")
        second = self.scan_element("192.168.20.10", "aa:bb:cc:dd:ee:20")
        stats = {"new_devices": 0, "ports_opened": 0, "ports_closed": 0}
        config = AppSettings.load()
        config.scan_ranges = ["192.168.1.0/24", "192.168.20.0/24"]
        config.scan_range_labels = {
            "192.168.1.0/24": "Main LAN",
            "192.168.20.0/24": "IoT",
        }
        config.save(update_fields=["scan_ranges", "scan_range_labels"])

        with (
            patch("core.scanning.orchestration.get_default_gateway_ip", return_value="192.168.1.1"),
            patch("core.scanning.orchestration.discover_devices", side_effect=[[first], [second]]) as discover,
            patch("core.scanning.orchestration.local_scanner_interface", return_value=None),
            patch("core.scanning.orchestration.discover_hostname_hints", return_value={}),
            patch("core.scanning.orchestration.ssdp_metadata_map", return_value={}),
            patch("core.scanning.orchestration.sync_discovered_device", return_value=stats) as sync_device,
            patch("core.scanning.orchestration.clear_stale_gateways"),
            patch("core.scanning.orchestration.mark_missing_devices_offline") as mark_missing,
        ):
            scan_run = scan(["192.168.1.0/24", "192.168.20.0/24"])

        self.assertEqual(
            [item.args[0] for item in discover.call_args_list],
            ["192.168.1.0/24", "192.168.20.0/24"],
        )
        self.assertEqual(sync_device.call_count, 2)
        self.assertEqual(scan_run.ip_range, "192.168.1.0/24")
        self.assertEqual(
            scan_run.scan_ranges,
            ["192.168.1.0/24", "192.168.20.0/24"],
        )
        self.assertEqual(
            scan_run.scan_range_labels,
            {
                "192.168.1.0/24": "Main LAN",
                "192.168.20.0/24": "IoT",
            },
        )
        self.assertEqual(scan_run.devices_seen, 2)
        mark_missing.assert_called_once_with(
            ["aa:bb:cc:dd:ee:10", "aa:bb:cc:dd:ee:20"],
            scan_run=scan_run,
            ip_ranges=["192.168.1.0/24", "192.168.20.0/24"],
        )

    @override_settings(
        SCAN_OFFLINE_AFTER_MISSES=1,
        SCAN_CONFIRM_OFFLINE_WITH_PORTS=False,
        SCAN_CONFIRM_OFFLINE_WITH_ICMP=False,
    )
    def test_missing_devices_are_scoped_to_scanned_ranges(self):
        inside = Device.objects.create(
            name="Inside",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:10",
            online=True,
        )
        outside = Device.objects.create(
            name="Outside",
            ip="192.168.20.10",
            mac="aa:bb:cc:dd:ee:20",
            online=True,
        )

        mark_missing_devices_offline([], ip_ranges=["192.168.1.0/24"])

        inside.refresh_from_db()
        outside.refresh_from_db()
        self.assertFalse(inside.online)
        self.assertTrue(outside.online)

    def test_validate_ip_ranges_normalizes_and_rejects_overlaps(self):
        self.assertEqual(
            validate_ip_ranges(["192.168.1.4/24", "192.168.20.0/24"]),
            ["192.168.1.0/24", "192.168.20.0/24"],
        )
        with self.assertRaisesMessage(ValueError, "must not overlap"):
            validate_ip_ranges(["192.168.1.0/24", "192.168.1.128/25"])

    @override_settings(SCAN_MAX_HOSTS=1024)
    def test_validate_ip_ranges_accepts_up_to_1024_addresses_per_range(self):
        self.assertEqual(
            validate_ip_ranges(["192.168.0.0/22"]),
            ["192.168.0.0/22"],
        )
        with self.assertRaisesMessage(ValueError, "Maximum allowed hosts: 1024"):
            validate_ip_ranges(["192.168.0.0/21"])

    @override_settings(SCAN_MAX_RANGES=2)
    def test_validate_ip_ranges_enforces_range_count_limit(self):
        with self.assertRaisesMessage(ValueError, "Maximum allowed ranges: 2"):
            validate_ip_ranges(
                ["192.168.1.0/24", "192.168.20.0/24", "192.168.30.0/24"]
            )

    @override_settings(SCAN_OFFLINE_AFTER_MISSES=3, PORT_SCAN_ENABLED=False)
    def test_missing_device_is_not_marked_offline_until_grace_limit(self):
        device = Device.objects.create(
            name="Router",
            ip="192.168.1.1",
            mac="aa:bb:cc:dd:ee:ff",
            online=True,
        )

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
        )
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 1)
        self.assertEqual(device.status, Device.Status.RECENTLY_SEEN)
        self.assertEqual(device.status_source, Device.StatusSource.RECENT)

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
        )
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 2)

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(
                ip_range="192.168.1.0/24",
                status=ScanRun.Status.SUCCESS,
            ),
        )
        device.refresh_from_db()
        self.assertFalse(device.online)
        self.assertEqual(device.missed_scans, 3)
        self.assertEqual(device.status, Device.Status.OFFLINE)
        self.assertEqual(device.status_source, Device.StatusSource.NONE)
        self.assertTrue(
            NetworkEvent.objects.filter(
                device=device,
                event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            ).exists()
        )

    @override_settings(
        SCAN_OFFLINE_AFTER_MISSES=1,
        PORT_SCAN_ENABLED=True,
        SCAN_CONFIRM_OFFLINE_WITH_PORTS=True,
        PORT_SCAN_PORTS=[22],
    )
    @patch("core.scanning.presence.scan_open_ports")
    def test_missing_device_stays_online_when_ports_respond(self, scan_open_ports):
        scan_open_ports.return_value = [{"port": 22, "protocol": "tcp", "service": "ssh"}]
        device = Device.objects.create(
            name="Server",
            ip="192.168.1.20",
            mac="aa:bb:cc:dd:ee:ff",
            online=True,
        )

        scan_run = ScanRun.objects.create(ip_range="192.168.1.0/24")
        mark_missing_devices_offline([], scan_run=scan_run)

        scan_open_ports.assert_called_once_with(device.ip, ports=[22])
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 0)
        self.assertIsNotNone(device.last_port_scan)
        self.assertEqual(device.status, Device.Status.ONLINE)
        self.assertEqual(device.status_source, Device.StatusSource.PORT)
        self.assertIn("tcp/22", device.status_reason)
        self.assertTrue(device.ports.filter(port=22, open=True).exists())
        self.assertFalse(
            NetworkEvent.objects.filter(
                device=device,
                event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            ).exists()
        )

    @override_settings(
        SCAN_OFFLINE_AFTER_MISSES=1,
        PORT_SCAN_ENABLED=True,
        SCAN_CONFIRM_OFFLINE_WITH_PORTS=True,
        PORT_SCAN_PORTS=[22],
    )
    @patch("core.scanning.presence.scan_open_ports")
    def test_missing_device_confirms_with_previously_open_ports(self, scan_open_ports):
        scan_open_ports.return_value = [{"port": 32400, "protocol": "tcp", "service": ""}]
        device = Device.objects.create(
            name="Media server",
            ip="192.168.1.30",
            mac="aa:bb:cc:dd:ee:ff",
            online=True,
        )
        DevicePort.objects.create(
            device=device,
            port=32400,
            protocol="tcp",
            service="",
            open=True,
        )

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        scan_open_ports.assert_called_once_with(device.ip, ports=[22, 32400])
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 0)
        self.assertEqual(device.status_source, Device.StatusSource.PORT)
        self.assertTrue(device.ports.filter(port=32400, open=True).exists())

    @override_settings(
        SCAN_OFFLINE_AFTER_MISSES=1,
        PORT_SCAN_ENABLED=False,
        SCAN_CONFIRM_OFFLINE_WITH_ICMP=True,
    )
    @patch("core.scanning.presence.scapy.sr1")
    def test_missing_device_stays_online_when_icmp_responds(self, sr1):
        sr1.return_value = object()
        device = Device.objects.create(
            name="Server",
            ip="192.168.1.20",
            mac="aa:bb:cc:dd:ee:ff",
            online=True,
        )

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 0)
        self.assertEqual(device.status, Device.Status.ONLINE)
        self.assertEqual(device.status_source, Device.StatusSource.ICMP)

    @override_settings(
        PORT_SCAN_ENABLED=False,
        SCAN_SLEEPING_OFFLINE_AFTER_MISSES=6,
    )
    def test_sleeping_device_gets_longer_grace_status(self):
        device = Device.objects.create(
            name="Bedroom light",
            ip="192.168.1.40",
            mac="aa:bb:cc:dd:ee:ff",
            icon="light",
            online=True,
        )

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 1)
        self.assertEqual(device.status, Device.Status.SLEEPING)

    @override_settings(
        PORT_SCAN_ENABLED=False,
        SCAN_MOBILE_OFFLINE_AFTER_MISSES=1,
        SCAN_CONFIRM_OFFLINE_WITH_ICMP=False,
    )
    def test_mobile_device_uses_shorter_offline_grace(self):
        device = Device.objects.create(
            name="Phone",
            ip="192.168.1.50",
            mac="aa:bb:cc:dd:ee:ff",
            icon="phone",
            online=True,
        )

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertFalse(device.online)
        self.assertEqual(device.status, Device.Status.OFFLINE)

    @override_settings(PORT_SCAN_ENABLED=True, PORT_SCAN_INTERVAL=30)
    @patch("core.scanning.reconciliation.scan_open_ports")
    def test_recently_port_scanned_device_skips_port_scan(self, scan_open_ports):
        device = Device.objects.create(
            name="Camera",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:ff",
            last_port_scan=timezone.now() - timedelta(minutes=10),
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        scan_open_ports.assert_not_called()
        device.refresh_from_db()
        self.assertEqual(device.missed_scans, 0)

    @override_settings(PORT_SCAN_ENABLED=True, PORT_SCAN_INTERVAL=30)
    @patch("core.scanning.reconciliation.scan_open_ports")
    def test_stale_port_scan_runs_and_updates_timestamp(self, scan_open_ports):
        scan_open_ports.return_value = []
        device = Device.objects.create(
            name="Camera",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:ff",
            last_port_scan=timezone.now() - timedelta(minutes=31),
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        scan_open_ports.assert_called_once_with(device.ip)
        device.refresh_from_db()
        self.assertIsNotNone(device.last_port_scan)

    def test_guess_device_identity_uses_hostname_before_vendor(self):
        identity = guess_device_identity(
            hostname="livingroom-streamer",
            vendor="Apple, Inc.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["name"], "livingroom-streamer")
        self.assertEqual(identity["icon"], "streamer")

    def test_guess_device_identity_uses_vendor_fallback_name(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="TP-Link Technologies Co., Ltd.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["name"], "TP-Link Technologies Co., Ltd.")
        self.assertEqual(identity["icon"], "unknown")

    def test_preferred_vendor_preserves_observed_vendor(self):
        self.assertEqual(
            preferred_vendor(observed_vendor="TP-Link Technologies Co., Ltd."),
            "TP-Link Technologies Co., Ltd.",
        )
        self.assertEqual(
            preferred_vendor(observed_vendor="Hon Hai Precision Industry Co.,Ltd."),
            "Hon Hai Precision Industry Co.,Ltd.",
        )

    @override_settings(PORT_SCAN_ENABLED=False)
    def test_existing_device_vendor_is_replaced_by_current_scan_vendor(self):
        device = Device.objects.create(
            name="Bedroom AC",
            ip="192.168.1.70",
            mac="aa:bb:cc:dd:ee:ff",
            vendor="Apple, Inc.",
            known=True,
        )

        with patch("core.scanning.reconciliation.ManufDA.lookup", return_value=("aa:bb:cc", "Texas Instruments")):
            sync_discovered_device(
                self.scan_element(device.ip, device.mac),
                oui=object(),
                scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
            )

        device.refresh_from_db()
        self.assertEqual(device.vendor, "Texas Instruments")
        self.assertEqual(device.name, "Bedroom AC")

    @override_settings(PORT_SCAN_ENABLED=False)
    def test_existing_device_vendor_is_cleared_when_current_scan_has_no_vendor(self):
        device = Device.objects.create(
            name="Bedroom AC",
            ip="192.168.1.70",
            mac="aa:bb:cc:dd:ee:ff",
            vendor="Apple, Inc.",
            known=True,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.vendor, "")
        self.assertEqual(device.name, "Bedroom AC")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value="")
    def test_existing_device_hostname_is_cleared_when_current_scan_has_no_hostname(self, _):
        device = Device.objects.create(
            name="Bedroom AC",
            ip="192.168.1.70",
            mac="aa:bb:cc:dd:ee:ff",
            hostname="Aqara Hub",
            known=True,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.hostname, "")
        self.assertEqual(device.name, "Bedroom AC")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value="office-laptop")
    def test_existing_device_preserves_user_selected_desktop_icon(self, _):
        device = Device.objects.create(
            name="Basement Desktop",
            ip="192.168.1.47",
            mac="08:62:66:50:bf:e2",
            icon="desktop",
            known=True,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.icon, "desktop")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value="office-laptop")
    def test_known_device_preserves_user_selected_unknown_icon(self, _):
        device = Device.objects.create(
            name="Office computer",
            ip="192.168.1.48",
            mac="08:62:66:50:bf:e3",
            icon="unknown",
            known=True,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.icon, "unknown")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value="office-laptop")
    def test_unknown_device_icon_continues_to_follow_identity_detection(self, _):
        device = Device.objects.create(
            name="Unreviewed device",
            ip="192.168.1.49",
            mac="08:62:66:50:bf:e4",
            icon="desktop",
            known=False,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.icon, "laptop")

    @override_settings(PORT_SCAN_ENABLED=True, PORT_SCAN_INTERVAL=30)
    @patch("core.scanning.reconciliation.scan_open_ports")
    def test_existing_device_port_enrichment_preserves_selected_icon(self, scan_open_ports):
        scan_open_ports.return_value = [{"port": 554, "protocol": "tcp", "service": "rtsp"}]
        device = Device.objects.create(
            name="Basement Desktop",
            ip="192.168.1.47",
            mac="08:62:66:50:bf:e2",
            icon="desktop",
            known=True,
            last_port_scan=timezone.now() - timedelta(minutes=31),
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.icon, "desktop")

    @override_settings(PORT_SCAN_ENABLED=True, PORT_SCAN_INTERVAL=30)
    @patch("core.scanning.reconciliation.scan_open_ports")
    def test_unknown_device_icon_continues_to_follow_port_detection(self, scan_open_ports):
        scan_open_ports.return_value = [{"port": 554, "protocol": "tcp", "service": "rtsp"}]
        device = Device.objects.create(
            name="Unreviewed device",
            ip="192.168.1.50",
            mac="08:62:66:50:bf:e5",
            icon="desktop",
            known=False,
            last_port_scan=timezone.now() - timedelta(minutes=31),
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device.refresh_from_db()
        self.assertEqual(device.icon, "security-camera")

    @patch("builtins.open")
    def test_default_gateway_from_proc_route(self, open_mock):
        open_mock.return_value.__enter__.return_value = iter(
            [
                "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n",
                "eth0 00000000 0100A8C0 0003 0 0 0 00000000 0 0 0\n",
            ]
        )

        self.assertEqual(default_gateway_from_proc_route(), "192.168.0.1")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname")
    def test_discovered_gateway_is_marked_known_router(self, get_hostname):
        get_hostname.return_value = "Device"

        sync_discovered_device(
            self.scan_element("192.168.0.1", "aa:bb:cc:dd:ee:ff"),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.0.0/24"),
            gateway_ip="192.168.0.1",
        )

        device = Device.objects.get(mac="aa:bb:cc:dd:ee:ff")
        self.assertTrue(device.is_gateway)
        self.assertTrue(device.known)
        self.assertEqual(device.name, "Gateway")
        self.assertEqual(device.icon, "router")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname")
    def test_existing_gateway_preserves_user_selected_role(self, get_hostname):
        get_hostname.return_value = "Deco X60"
        device = Device.objects.create(
            name="Main Deco",
            ip="192.168.0.1",
            mac="3c:6a:d2:f4:07:7c",
            role="meshRouter",
            known=True,
            is_gateway=True,
            icon="router",
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.0.0/24"),
            gateway_ip=device.ip,
        )

        device.refresh_from_db()
        self.assertTrue(device.is_gateway)
        self.assertEqual(device.role, "meshRouter")
        self.assertEqual(device.hostname, "Deco X60")
        self.assertEqual(device.vendor, "TP-Link Systems Inc.")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname", return_value="gateway.local")
    def test_existing_gateway_preserves_user_selected_icon(self, _):
        device = Device.objects.create(
            name="Main gateway",
            ip="192.168.0.1",
            mac="3c:6a:d2:f4:07:7d",
            icon="server",
            known=True,
        )

        sync_discovered_device(
            self.scan_element(device.ip, device.mac),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.0.0/24"),
            gateway_ip=device.ip,
        )

        device.refresh_from_db()
        self.assertTrue(device.is_gateway)
        self.assertEqual(device.icon, "server")

    def test_clear_stale_gateways_keeps_current_gateway_only(self):
        current = Device.objects.create(
            name="Current router",
            ip="192.168.0.1",
            mac="aa:bb:cc:dd:ee:01",
            is_gateway=True,
        )
        stale = Device.objects.create(
            name="Old router",
            ip="192.168.0.254",
            mac="aa:bb:cc:dd:ee:02",
            is_gateway=True,
        )

        clear_stale_gateways("192.168.0.1")

        current.refresh_from_db()
        stale.refresh_from_db()
        self.assertTrue(current.is_gateway)
        self.assertFalse(stale.is_gateway)

    def test_guess_device_identity_uses_plain_vendor_without_mac_suffix(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="Hon Hai Precision Industry",
            mac="11:22:33:44:1b:53",
        )

        self.assertEqual(identity["name"], "Hon Hai Precision Industry")

    def test_guess_device_identity_uses_original_vendor_name(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="Espressif Inc.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["name"], "Espressif Inc.")

    def test_guess_device_identity_uses_private_mac_fallback_name(self):
        identity = guess_device_identity(
            hostname="",
            vendor="",
            mac="c6:f5:3a:d8:da:f0",
        )

        self.assertEqual(identity["name"], "Private Device DAF0")

    def test_guess_device_identity_uses_unknown_mac_fallback_name(self):
        identity = guess_device_identity(
            hostname="",
            vendor="",
            mac="00:11:22:33:44:55",
        )

        self.assertEqual(identity["name"], "Unknown Device 4455")

    def test_mac_address_name_is_treated_as_default_name(self):
        identity = guess_device_identity(
            hostname="c6:f5:3a:d8:da:f0",
            vendor="",
            mac="c6:f5:3a:d8:da:f0",
        )

        self.assertEqual(identity["name"], "Private Device DAF0")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.reconciliation.get_hostname")
    def test_new_discovered_device_gets_guessed_name_and_icon(self, get_hostname):
        get_hostname.return_value = "livingroom-camera"

        sync_discovered_device(
            self.scan_element("192.168.1.25", "aa:bb:cc:dd:ee:ff"),
            oui=None,
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )

        device = Device.objects.get(mac="aa:bb:cc:dd:ee:ff")
        self.assertEqual(device.name, "livingroom-camera")
        self.assertEqual(device.icon, "security-camera")

    def test_guess_device_identity_detects_shutter(self):
        identity = guess_device_identity(
            hostname="bedroom-shutter",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "shutter")

    def test_guess_device_identity_detects_smart_hub(self):
        identity = guess_device_identity(
            hostname="home hub",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "smart-hub")

    def test_guess_device_identity_detects_desk_lamp(self):
        identity = guess_device_identity(
            hostname="office desk lamp",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "desk-lamp")

    def test_guess_device_identity_detects_led_strip(self):
        identity = guess_device_identity(
            hostname="kitchen led strip",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "led-strip")

    def test_guess_device_identity_detects_ceiling_light(self):
        identity = guess_device_identity(
            hostname="hall ceiling light",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "ceiling-light")

    def test_guess_device_identity_detects_air_conditioner(self):
        identity = guess_device_identity(
            hostname="bedroom-air-conditioner",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "air-conditioner")

    def test_guess_device_identity_detects_cast_ports(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
            open_ports=[{"port": 8009}],
        )

        self.assertEqual(identity["icon"], "streamer")

    def test_guess_device_identity_detects_rtsp_port(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="",
            mac="aa:bb:cc:dd:ee:ff",
            open_ports=[554],
        )

        self.assertEqual(identity["icon"], "security-camera")

    def test_guess_device_identity_detects_tablet_watch_and_fan(self):
        self.assertEqual(
            guess_device_identity(
                hostname="kids tablet",
                vendor="",
                mac="aa:bb:cc:dd:ee:ff",
            )["icon"],
            "tablet",
        )
        self.assertEqual(
            guess_device_identity(
                hostname="apple watch",
                vendor="",
                mac="aa:bb:cc:dd:ee:ff",
            )["icon"],
            "smart-watch",
        )
        self.assertEqual(
            guess_device_identity(
                hostname="livingroom ceiling fan",
                vendor="",
                mac="aa:bb:cc:dd:ee:ff",
            )["icon"],
            "ceiling-fan",
        )

    def test_guess_device_identity_detects_requested_device_categories(self):
        examples = {
            "PlayStation 5": "game-console",
            "Office notebook": "laptop",
            "Synology NAS": "nas",
            "Garage smart relay": "smart-relay",
            "Desk smart power strip": "smart-power-strip",
            "Main energy meter": "power-meter",
        }

        for hostname, expected_icon in examples.items():
            with self.subTest(hostname=hostname):
                identity = guess_device_identity(
                    hostname=hostname,
                    vendor="",
                    mac="90:dd:5d:b7:bd:01",
                )
                self.assertEqual(identity["icon"], expected_icon)
