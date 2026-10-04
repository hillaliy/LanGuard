from datetime import timedelta
import importlib
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.core.management import call_command
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ..management.commands.run_scheduler import load_scan_schedule
from ..models import (
    AppSettings,
    ScanRun,
)
from ..scanning.lifecycle import (
    STALE_SCAN_ERROR,
    ScanAlreadyRunning,
    active_scan_run,
    claim_scan_run,
    scan_failure_diagnostics,
)
from ..scanning.orchestration import scan

class ScanCommandTests(TestCase):
    def test_scheduler_reloads_saved_ranges_and_interval(self):
        config = AppSettings.load()
        config.ip_range = "192.168.1.0/24"
        config.scan_ranges = ["192.168.1.0/24"]
        config.scan_interval = 10
        config.save(update_fields=["ip_range", "scan_ranges", "scan_interval"])

        self.assertEqual(
            load_scan_schedule(),
            (["192.168.1.0/24"], 10),
        )

        config.scan_ranges = ["192.168.20.0/24", "192.168.30.0/24"]
        config.scan_interval = 25
        config.save(update_fields=["scan_ranges", "scan_interval"])

        self.assertEqual(
            load_scan_schedule(),
            (["192.168.20.0/24", "192.168.30.0/24"], 25),
        )

    def test_scheduler_keeps_explicit_command_overrides(self):
        self.assertEqual(
            load_scan_schedule(["10.0.0.0/24"], 30),
            (["10.0.0.0/24"], 30),
        )

    @patch("core.management.commands.run_scheduler.signal.signal")
    @patch("core.management.commands.run_scheduler.threading.Thread")
    @patch("core.management.commands.run_scheduler.threading.Event")
    @patch("core.management.commands.run_scheduler.scan")
    def test_scheduler_uses_latest_ranges_when_cycle_starts(
        self,
        scan_mock,
        event_factory,
        thread_factory,
        signal_mock,
    ):
        config = AppSettings.load()
        config.ip_range = "192.168.1.0/24"
        config.scan_ranges = ["192.168.1.0/24"]
        config.scan_interval = 10
        config.save(update_fields=["ip_range", "scan_ranges", "scan_interval"])
        stop_event = Mock()
        stop_event.is_set.side_effect = [False, True]

        def finish_wait(_seconds):
            config.scan_ranges = ["192.168.20.0/24", "192.168.30.0/24"]
            config.scan_interval = 25
            config.save(update_fields=["scan_ranges", "scan_interval"])
            return False

        stop_event.wait.side_effect = finish_wait
        event_factory.return_value = stop_event

        call_command("run_scheduler")

        scan_mock.assert_called_once_with(
            ["192.168.20.0/24", "192.168.30.0/24"],
            source=ScanRun.Source.SCHEDULED,
        )
        thread_factory.assert_called()
        thread_targets = {
            call.kwargs["target"].__name__
            for call in thread_factory.call_args_list
        }
        self.assertIn("speedtest_health_loop", thread_targets)
        signal_mock.assert_called()

    @patch("core.management.commands.run_scheduler.signal.signal")
    @patch("core.management.commands.run_scheduler.threading.Thread")
    @patch("core.management.commands.run_scheduler.threading.Event")
    @patch("core.management.commands.run_scheduler.scan")
    def test_scheduler_retries_after_manual_scan_conflict(
        self,
        scan_mock,
        event_factory,
        _,
        __,
    ):
        active_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            source=ScanRun.Source.MANUAL,
        )
        scan_mock.side_effect = [ScanAlreadyRunning(active_scan), None]
        stop_event = Mock()
        stop_event.is_set.side_effect = [False, False, True]
        stop_event.wait.return_value = False
        event_factory.return_value = stop_event
        output = StringIO()

        call_command("run_scheduler", stdout=output)

        self.assertIn("Scheduled scan skipped", output.getvalue())
        self.assertEqual(scan_mock.call_count, 2)
        scan_mock.assert_has_calls(
            [
                call(
                    ["192.168.1.0/24"],
                    source=ScanRun.Source.SCHEDULED,
                ),
                call(
                    ["192.168.1.0/24"],
                    source=ScanRun.Source.SCHEDULED,
                ),
            ]
        )

    @patch("core.management.commands.scan_network.scan")
    def test_scan_network_accepts_repeated_ranges(self, scan_mock):
        call_command(
            "scan_network",
            "--ip-range",
            "192.168.1.0/24",
            "--ip-range",
            "192.168.20.0/24",
        )

        scan_mock.assert_called_once_with(
            ["192.168.1.0/24", "192.168.20.0/24"],
            source=ScanRun.Source.COMMAND,
        )
class ScanLockTests(TestCase):
    def test_only_one_network_scan_can_be_claimed(self):
        first_scan = claim_scan_run(
            ["192.168.1.0/24"],
            {},
            ScanRun.Source.MANUAL,
        )

        with self.assertRaises(ScanAlreadyRunning) as context:
            claim_scan_run(
                ["192.168.20.0/24"],
                {},
                ScanRun.Source.SCHEDULED,
            )

        self.assertEqual(context.exception.active_scan.id, first_scan.id)
        self.assertEqual(ScanRun.objects.filter(status=ScanRun.Status.RUNNING).count(), 1)

    @override_settings(SCAN_LOCK_STALE_SECONDS=60)
    def test_stale_network_scan_is_failed_before_new_scan_is_claimed(self):
        stale_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            source=ScanRun.Source.MANUAL,
            heartbeat_at=timezone.now() - timedelta(minutes=2),
        )

        replacement = claim_scan_run(
            ["192.168.20.0/24"],
            {},
            ScanRun.Source.SCHEDULED,
        )

        stale_scan.refresh_from_db()
        self.assertEqual(stale_scan.status, ScanRun.Status.FAILED)
        self.assertEqual(stale_scan.error, STALE_SCAN_ERROR)
        self.assertEqual(stale_scan.failure_code, "stale_scan_lock")
        self.assertEqual(stale_scan.failure_stage, "heartbeat")
        self.assertEqual(active_scan_run().id, replacement.id)

    def test_database_lock_diagnostics_do_not_store_raw_error(self):
        details = scan_failure_diagnostics(
            OperationalError("database is locked for private-device-name"),
            "device_sync",
        )

        self.assertEqual(details["code"], "database_locked")
        self.assertEqual(details["type"], "OperationalError")
        self.assertEqual(details["stage"], "device_sync")
        self.assertEqual(len(details["fingerprint"]), 16)
        self.assertNotIn("private-device-name", str(details))

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scanning.orchestration.get_default_gateway_ip", return_value="192.168.1.1")
    @patch("core.scanning.orchestration.discover_devices", side_effect=RuntimeError("scanner stopped"))
    def test_failed_scan_releases_lock(self, _, __):
        with self.assertRaisesRegex(RuntimeError, "scanner stopped"):
            scan(["192.168.1.0/24"], source=ScanRun.Source.MANUAL)

        failed_scan = ScanRun.objects.get()
        self.assertEqual(failed_scan.status, ScanRun.Status.FAILED)
        self.assertIsNotNone(failed_scan.finished_at)
        self.assertEqual(failed_scan.failure_code, "unexpected_error")
        self.assertEqual(failed_scan.failure_type, "RuntimeError")
        self.assertEqual(failed_scan.failure_stage, "arp_discovery")
        self.assertEqual(len(failed_scan.failure_fingerprint), 16)

        replacement = claim_scan_run(
            ["192.168.1.0/24"],
            {},
            ScanRun.Source.SCHEDULED,
        )
        self.assertEqual(replacement.status, ScanRun.Status.RUNNING)
class MultiNetworkMigrationTests(SimpleTestCase):
    def test_migration_copies_primary_range_to_new_fields(self):
        migration = importlib.import_module(
            "core.migrations.0028_multi_network_scan_ranges"
        )
        config = SimpleNamespace(
            ip_range="192.168.1.0/24",
            scan_ranges=[],
            save=Mock(),
        )
        scan_run = SimpleNamespace(
            ip_range="192.168.20.0/24",
            scan_ranges=[],
            save=Mock(),
        )
        config_queryset = Mock()
        config_queryset.iterator.return_value = iter([config])
        run_queryset = Mock()
        run_queryset.iterator.return_value = iter([scan_run])
        app_settings_model = Mock()
        app_settings_model.objects.all.return_value = config_queryset
        scan_run_model = Mock()
        scan_run_model.objects.all.return_value = run_queryset
        apps = Mock()
        apps.get_model.side_effect = [app_settings_model, scan_run_model]

        migration.copy_primary_ranges(apps, None)

        self.assertEqual(config.scan_ranges, ["192.168.1.0/24"])
        self.assertEqual(scan_run.scan_ranges, ["192.168.20.0/24"])
        config.save.assert_called_once_with(update_fields=["scan_ranges"])
        scan_run.save.assert_called_once_with(update_fields=["scan_ranges"])

    def test_label_migration_names_configured_ranges_and_matching_scan_history(self):
        migration = importlib.import_module("core.migrations.0029_scan_range_labels")
        config = SimpleNamespace(
            ip_range="192.168.1.0/24",
            scan_ranges=["192.168.1.0/24", "192.168.20.0/24"],
            scan_range_labels={},
            save=Mock(),
        )
        matching_run = SimpleNamespace(
            ip_range="192.168.20.0/24",
            scan_ranges=["192.168.20.0/24"],
            scan_range_labels={},
            save=Mock(),
        )
        unrelated_run = SimpleNamespace(
            ip_range="192.168.30.0/24",
            scan_ranges=["192.168.30.0/24"],
            scan_range_labels={},
            save=Mock(),
        )
        app_settings_model = Mock()
        app_settings_model.objects.first.return_value = config
        run_queryset = Mock()
        run_queryset.iterator.return_value = iter([matching_run, unrelated_run])
        scan_run_model = Mock()
        scan_run_model.objects.all.return_value = run_queryset
        apps = Mock()
        apps.get_model.side_effect = [app_settings_model, scan_run_model]

        migration.populate_scan_range_labels(apps, None)

        expected_labels = {
            "192.168.1.0/24": "Primary network",
            "192.168.20.0/24": "Network 2",
        }
        self.assertEqual(config.scan_range_labels, expected_labels)
        self.assertEqual(
            matching_run.scan_range_labels,
            {"192.168.20.0/24": "Network 2"},
        )
        self.assertEqual(unrelated_run.scan_range_labels, {})
        config.save.assert_called_once_with(update_fields=["scan_range_labels"])
        matching_run.save.assert_called_once_with(update_fields=["scan_range_labels"])
        unrelated_run.save.assert_called_once_with(update_fields=["scan_range_labels"])
