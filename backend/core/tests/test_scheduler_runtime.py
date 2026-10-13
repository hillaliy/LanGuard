from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from ..management.commands.run_scheduler import wait_for_next_scheduled_scan
from ..models import AppSettings, SchedulerRuntimeState
from ..scheduler_runtime import (
    scheduler_runtime_payload,
    set_next_scheduled_scan,
    start_scheduler_runtime,
    stop_scheduler_runtime,
    touch_scheduler_runtime,
)


class SchedulerRuntimeStateTests(TestCase):
    @override_settings(SCHEDULER_HEARTBEAT_STALE_SECONDS=60)
    def test_runtime_lifecycle_exposes_only_active_schedule(self):
        now = timezone.now()
        next_scan_at = now + timedelta(minutes=10)

        start_scheduler_runtime(now)
        set_next_scheduled_scan(next_scan_at, now)

        payload = scheduler_runtime_payload(now=now)
        self.assertEqual(payload["status"], "scheduled")
        self.assertTrue(payload["available"])
        self.assertIsNotNone(payload["next_scan_at"])

        touch_scheduler_runtime(now + timedelta(seconds=15))
        scanning = scheduler_runtime_payload(
            scheduled_scan_running=True,
            now=now + timedelta(seconds=15),
        )
        self.assertEqual(scanning["status"], "scanning")
        self.assertIsNone(scanning["next_scan_at"])

        stop_scheduler_runtime(now + timedelta(seconds=20))
        stopped = scheduler_runtime_payload(now=now + timedelta(seconds=20))
        self.assertEqual(stopped["status"], "unavailable")
        self.assertFalse(stopped["available"])

    @override_settings(SCHEDULER_HEARTBEAT_STALE_SECONDS=60)
    def test_stale_heartbeat_does_not_expose_timestamp(self):
        now = timezone.now()
        SchedulerRuntimeState.objects.create(
            heartbeat_at=now - timedelta(seconds=61),
            next_scan_at=now + timedelta(minutes=5),
        )

        payload = scheduler_runtime_payload(now=now)

        self.assertEqual(payload["status"], "unavailable")
        self.assertIsNone(payload["next_scan_at"])

    @override_settings(SCHEDULER_SCHEDULE_POLL_SECONDS=15)
    def test_wait_recalculates_target_when_interval_changes(self):
        anchor = datetime(2026, 10, 13, 12, 0)
        current_time = [anchor]
        config = AppSettings.load()
        config.scan_interval = 10
        config.save(update_fields=["scan_interval"])
        stop_event = Mock()
        stop_event.is_set.return_value = False

        def advance_time(seconds):
            current_time[0] += timedelta(seconds=seconds)
            if config.scan_interval != 1:
                config.scan_interval = 1
                config.save(update_fields=["scan_interval"])
            return False

        stop_event.wait.side_effect = advance_time

        with patch(
            "core.management.commands.run_scheduler.timezone.now",
            side_effect=lambda: current_time[0],
        ):
            should_scan = wait_for_next_scheduled_scan(stop_event, anchor)

        self.assertTrue(should_scan)
        state = SchedulerRuntimeState.objects.get(singleton_key=1)
        self.assertEqual(state.next_scan_at, anchor + timedelta(minutes=1))
