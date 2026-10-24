import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..integrations.dhcp import DhcpError, parse_leases, read_lease_file, sync_dhcp
from ..models import AppSettings, Device, DeviceIPAddressAssignment


MAC = "02:11:22:33:44:55"


class DhcpParserTests(SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()
        self.future = int((self.now + timedelta(days=1)).timestamp())

    def test_dnsmasq_expiry_infinite_and_invalid_addresses(self):
        text = (
            f"{self.future} {MAC} 192.168.1.20 laptop *\n"
            f"0 02:11:22:33:44:56 192.168.1.21 * *\n"
            f"1 02:11:22:33:44:57 192.168.1.22 old *\n"
            f"0 ff:ff:ff:ff:ff:ff 192.168.1.23 bad *\n"
            f"0 02:11:22:33:44:58 8.8.8.8 public *\n"
            f"0 {MAC} 2001:db8::1 ipv6 *\n"
            "duid 00:01:00:01:22:33\n"
        )
        leases, summary = parse_leases(text, "dnsmasq", self.now)
        self.assertEqual([item["ip"] for item in leases], ["192.168.1.20", "192.168.1.21"])
        self.assertEqual(leases[1]["name"], "")
        self.assertEqual(summary, {"active_leases": 2, "expired_leases": 1, "invalid_leases": 3})

    def test_kea_latest_journal_record_wins_including_releases_and_zero_lifetime(self):
        header = "address,hwaddr,valid_lifetime,expire,hostname,state\n"
        text = header + (
            f"192.168.1.20,{MAC},3600,{self.future},laptop,0\n"
            f"192.168.1.20,{MAC},3600,{self.future},laptop,3\n"
            f"192.168.1.21,{MAC},3600,{self.future},old,0\n"
            f"192.168.1.21,{MAC},0,{self.future},old,0\n"
            f"192.168.1.22,{MAC},4294967295,1,infinite,0\n"
            "192.168.1.23,02:11:22:33:44:56,3600,0,expired,0\n"
        )
        leases, summary = parse_leases(text, "kea", self.now)
        self.assertEqual([item["ip"] for item in leases], ["192.168.1.22"])
        self.assertEqual(summary["expired_leases"], 3)

    def test_kea_older_header_and_csv_quoted_hostname(self):
        text = f'address,hwaddr,valid_lifetime,expire,hostname\n192.168.1.20,{MAC},3600,{self.future},"laptop"\n'
        leases, _ = parse_leases(text, "kea", self.now)
        self.assertEqual(leases[0]["name"], "laptop")

    def test_isc_blocks_comments_nested_statements_and_latest_state(self):
        text = f'''
        # A journal contains previous states of the same IP.
        lease 192.168.1.20 {{
          ends never;
          binding state active;
          hardware ethernet {MAC};
          client-hostname "laptop";
          on expiry {{ set message = "ends never; }}"; }}
          on release {{ set message = "}}"; }}
        }}
        lease 192.168.1.20 {{ ends never; binding state free; }}
        lease 192.168.1.21 {{
          ends epoch {self.future}; binding state active;
          hardware ethernet {MAC}; client-hostname "new-laptop";
        }}
        '''
        leases, summary = parse_leases(text, "isc", self.now)
        self.assertEqual([item["ip"] for item in leases], ["192.168.1.21"])
        self.assertEqual(summary["expired_leases"], 1)

    def test_isc_utc_end_date_and_expiry(self):
        end = (self.now + timedelta(days=1)).strftime("%Y/%m/%d %H:%M:%S")
        text = f'lease 192.168.1.20 {{ ends 6 {end}; binding state active; hardware ethernet {MAC}; }}'
        self.assertEqual(parse_leases(text, "isc", self.now)[1]["active_leases"], 1)
        self.assertEqual(parse_leases(text, "isc", self.now + timedelta(days=2))[1]["active_leases"], 0)

    def test_incomplete_files_fail_before_import(self):
        for source_format, text in [
            ("dnsmasq", "0 missing-fields"),
            ("kea", "address,hostname\n192.168.1.20,laptop"),
            ("kea", "address,hwaddr,valid_lifetime,expire,hostname\n192.168.1.20"),
            ("isc", f"lease 192.168.1.20 {{ hardware ethernet {MAC};"),
        ]:
            with self.subTest(source_format=source_format), self.assertRaises(DhcpError):
                parse_leases(text, source_format, self.now)

    def test_empty_source_is_valid_and_bounds_are_enforced(self):
        for source_format in ["dnsmasq", "kea", "isc"]:
            self.assertEqual(parse_leases("", source_format)[0], [])
        with patch("core.integrations.dhcp.MAX_RECORDS", 1), self.assertRaises(DhcpError):
            parse_leases(f"0 {MAC} 192.168.1.20 a *\n0 {MAC} 192.168.1.21 b *\n", "dnsmasq")


class DhcpSourceTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = self.settings(DHCP_LEASE_DIRECTORY=self.directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.path = Path(self.directory.name) / "dnsmasq.leases"
        self.config = AppSettings.load()
        self.config.dhcp_enabled = True
        self.config.dhcp_lease_file = self.path.name
        self.config.save()
        self.now = timezone.now()
        self.observed = self.now - timedelta(minutes=1)

    def write(self, text):
        self.path.write_text(text)
        stamp = self.observed.timestamp()
        os.utime(self.path, (stamp, stamp))

    def lease(self, ip="192.168.1.20", name="laptop", mac=MAC):
        return f"{int((self.now + timedelta(days=1)).timestamp())} {mac} {ip} {name} *\n"

    def device(self, **overrides):
        values = dict(mac=MAC, ip="192.168.1.10", name="Device", lastseen=self.now - timedelta(days=1))
        values.update(overrides)
        device = Device(**values)
        device.save(ip_observed_at=self.now - timedelta(days=1))
        return device

    def test_creation_is_opt_in_and_does_not_mark_devices_online(self):
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["devices_discovered"], 0)
        self.assertEqual(Device.objects.count(), 0)
        self.config.dhcp_create_devices = True
        self.config.save()
        result = sync_dhcp()
        device = Device.objects.get(mac=MAC)
        self.assertEqual(result["devices_discovered"], 1)
        self.assertFalse(device.online)
        self.assertFalse(device.known)
        self.assertEqual(device.hostname_source, Device.IdentitySource.DHCP)
        lastseen = device.lastseen
        self.assertEqual(sync_dhcp()["devices_updated"], 0)
        device.refresh_from_db()
        self.assertEqual(device.lastseen, lastseen)
        self.assertEqual(Device.objects.count(), 1)

    def test_enrichment_preserves_presence_and_known_identity(self):
        device = self.device(known=True, name="My custom name", hostname="manual-host", hostname_source="mdns")
        lastseen = device.lastseen
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["devices_updated"], 1)
        device.refresh_from_db()
        self.assertEqual(device.ip, "192.168.1.20")
        self.assertEqual(device.name, "My custom name")
        self.assertEqual(device.hostname, "manual-host")
        self.assertEqual(device.lastseen, lastseen)
        self.assertEqual(device.ip_assignments.filter(valid_until__isnull=True).get().ip, device.ip)

    def test_unknown_identity_is_enriched_but_controller_identity_is_not_overwritten(self):
        device = self.device()
        self.write(self.lease())
        sync_dhcp()
        device.refresh_from_db()
        self.assertEqual(device.hostname, "laptop")
        device.hostname = "controller-name"
        device.hostname_source = Device.IdentitySource.TECHNITIUM
        device.save(update_fields=["hostname", "hostname_source"])
        sync_dhcp()
        device.refresh_from_db()
        self.assertEqual(device.hostname, "controller-name")

    def test_conflict_does_not_reassign_ip_or_close_competing_assignment(self):
        device = self.device()
        competing = self.device(mac="02:11:22:33:44:56", ip="192.168.1.20", lastseen=self.now)
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["identity_conflicts"], 1)
        device.refresh_from_db()
        competing.refresh_from_db()
        self.assertEqual(device.ip, "192.168.1.10")
        self.assertTrue(device.identity_conflict_reason)
        self.assertTrue(competing.identity_conflict_reason)
        self.assertTrue(DeviceIPAddressAssignment.objects.filter(device=competing, valid_until__isnull=True).exists())

    def test_older_snapshot_does_not_replace_newer_ip_evidence(self):
        device = self.device(lastseen=self.now)
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["devices_skipped"], 1)
        device.refresh_from_db()
        self.assertEqual(device.ip, "192.168.1.10")

    def test_conflict_does_not_replace_newer_conflict_details(self):
        device = self.device()
        competing = self.device(
            mac="02:11:22:33:44:56", ip="192.168.1.20", lastseen=self.now,
            identity_conflict_reason="Newer conflict", identity_conflict_detected_at=self.now,
        )
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["identity_conflicts"], 1)
        competing.refresh_from_db()
        device.refresh_from_db()
        self.assertEqual(competing.identity_conflict_reason, "Newer conflict")
        self.assertEqual(competing.identity_conflict_detected_at, self.now)
        self.assertTrue(device.identity_conflict_reason)

    def test_recent_ip_assignment_is_preserved_even_without_recent_presence(self):
        device = self.device()
        competing = self.device(mac="02:11:22:33:44:56", ip="192.168.1.20")
        assignment = competing.ip_assignments.get(valid_until__isnull=True)
        assignment.valid_from = self.now
        assignment.save(update_fields=["valid_from"])
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["identity_conflicts"], 1)
        device.refresh_from_db()
        self.assertEqual(device.ip, "192.168.1.10")
        assignment.refresh_from_db()
        self.assertIsNone(assignment.valid_until)

    def test_stale_ip_assignment_is_closed_after_uncontested_reassignment(self):
        self.device()
        competing = self.device(mac="02:11:22:33:44:56", ip="192.168.1.20")
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["devices_updated"], 1)
        assignment = competing.ip_assignments.get()
        self.assertIsNotNone(assignment.valid_until)

    def test_missing_expired_and_archived_devices_are_not_removed_or_reactivated(self):
        device = self.device(archived=True)
        self.write(self.lease())
        self.assertEqual(sync_dhcp()["devices_skipped"], 1)
        device.refresh_from_db()
        self.assertTrue(device.archived)
        self.write("")
        sync_dhcp()
        self.assertTrue(Device.objects.filter(pk=device.pk).exists())

    def test_malformed_file_cannot_partially_modify_devices(self):
        device = self.device()
        self.write(self.lease() + "invalid line\n")
        with self.assertRaises(DhcpError):
            sync_dhcp()
        device.refresh_from_db()
        self.assertEqual(device.ip, "192.168.1.10")
        self.config.refresh_from_db()
        self.assertTrue(self.config.dhcp_last_error)
        self.assertIsNone(self.config.dhcp_last_sync_at)

    def test_duplicate_mac_with_multiple_active_ips_is_skipped(self):
        self.config.dhcp_create_devices = True
        self.config.save()
        self.write(self.lease() + self.lease(ip="192.168.1.21"))
        self.assertEqual(sync_dhcp()["devices_skipped"], 2)
        self.assertFalse(Device.objects.exists())

    def test_source_path_is_confined_and_regular_with_size_limit(self):
        self.write(self.lease())
        for name in ["../outside", str(self.path), ".", "invalid\x00name"]:
            with self.subTest(name=name), self.assertRaises(DhcpError):
                read_lease_file(name)
        with TemporaryDirectory() as outside:
            target = Path(outside) / "leases"
            target.write_text(self.lease())
            link = Path(self.directory.name) / "link"
            link.symlink_to(target)
            with self.assertRaises(DhcpError):
                read_lease_file("link")
        fifo = Path(self.directory.name) / "fifo"
        os.mkfifo(fifo)
        with self.assertRaises(DhcpError):
            read_lease_file("fifo")
        with patch("core.integrations.dhcp.MAX_FILE_BYTES", 1), self.assertRaises(DhcpError):
            read_lease_file(self.path.name)

    def test_disabled_sync_does_not_read_source(self):
        self.config.dhcp_enabled = False
        self.config.save()
        with patch("core.integrations.dhcp.inspect_lease_source") as inspect:
            self.assertEqual(sync_dhcp(), {"status": "disabled"})
            inspect.assert_not_called()

    def test_api_is_admin_only_and_test_source_does_not_write_devices(self):
        client = APIClient()
        user = User.objects.create_user(username="viewer", password="password")
        client.force_authenticate(user)
        self.write(self.lease())
        self.assertEqual(client.post("/api/v1/integrations/dhcp/sync/").status_code, 403)
        self.assertEqual(client.post("/api/v1/integrations/dhcp/test/").status_code, 403)
        user.is_staff = True
        user.save()
        client.force_authenticate(user)
        response = client.post("/api/v1/integrations/dhcp/test/", {"lease_file": self.path.name, "format": "dnsmasq"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Device.objects.exists())
        self.config.refresh_from_db()
        self.assertIsNone(self.config.dhcp_last_sync_at)
        response = client.post("/api/v1/integrations/dhcp/sync/")
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertIsNotNone(self.config.dhcp_last_sync_at)

    def test_settings_require_source_and_validate_paths_format_and_interval(self):
        from ..serializers.settings import AppSettingsSerializer
        for data in [
            {"dhcp_enabled": True, "dhcp_lease_file": ""},
            {"dhcp_lease_file": "../outside"}, {"dhcp_format": "unsupported"},
            {"dhcp_sync_interval": 0}, {"dhcp_sync_interval": 1441},
        ]:
            with self.subTest(data=data):
                serializer = AppSettingsSerializer(self.config, data=data, partial=True)
                self.assertFalse(serializer.is_valid())
        payload = AppSettingsSerializer(self.config).data
        self.assertTrue(payload["dhcp_configured"])
        self.assertFalse(payload["dhcp_create_devices"])
