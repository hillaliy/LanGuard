from unittest.mock import Mock, patch

from django.test import TestCase

from .models import AppSettings, NetworkEvent
from .notifications import format_discord_payload, notification_event_allowed
from .serializers import AppSettingsSerializer
from .speedtest_tracker import SpeedtestTrackerError, check_speedtest_health_change


class SpeedtestHealthNotificationTests(TestCase):
    def setUp(self):
        self.config = AppSettings.load()
        self.config.speedtest_tracker_enabled = True
        self.config.speedtest_tracker_url = "http://speedtest.example:8080"
        self.config.speedtest_tracker_api_token = "private-api-token"
        self.config.notify_speedtest_changes = True
        self.config.save()

    def result(self, result_id, healthy):
        return {
            "id": result_id,
            "healthy": healthy,
            "download_mbps": 700.5,
            "upload_mbps": 200.25,
            "ping_ms": 8.4,
            "packet_loss_percent": 0.0,
            "tested_at": "2026-09-14T17:00:00Z",
            "service_url": "http://speedtest.example:8080",
        }

    @patch("core.speedtest_tracker.notify_event")
    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_first_scored_result_establishes_baseline(self, latest, notify):
        latest.return_value = (self.result(10, True), False)

        result = check_speedtest_health_change()

        self.assertEqual(result, {"status": "baseline", "result_id": "10"})
        self.config.refresh_from_db()
        self.assertEqual(self.config.speedtest_last_result_id, "10")
        self.assertTrue(self.config.speedtest_last_healthy)
        notify.assert_not_called()
        self.assertFalse(NetworkEvent.objects.exists())

    @patch("core.speedtest_tracker.notify_event", return_value=[Mock()])
    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_health_change_creates_event_and_notification(self, latest, notify):
        self.config.speedtest_last_result_id = "10"
        self.config.speedtest_last_healthy = True
        self.config.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )
        latest.return_value = (self.result(11, False), False)

        result = check_speedtest_health_change()

        self.assertEqual(result["status"], "notified")
        self.assertEqual(result["health"], "degraded")
        event = NetworkEvent.objects.get(
            event_type=NetworkEvent.EventType.SPEEDTEST_HEALTH_CHANGED
        )
        self.assertIn("Healthy to Degraded", event.message)
        self.assertEqual(event.metadata["result_id"], "11")
        self.assertEqual(event.metadata["current_health"], "degraded")
        self.assertEqual(event.metadata["download_mbps"], 700.5)
        notify.assert_called_once_with(event)

    @patch("core.speedtest_tracker.notify_event", return_value=[])
    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_recovery_uses_healthy_state(self, latest, notify):
        self.config.speedtest_last_result_id = "11"
        self.config.speedtest_last_healthy = False
        self.config.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )
        latest.return_value = (self.result(12, True), False)

        result = check_speedtest_health_change()

        self.assertEqual(result["health"], "healthy")
        event = NetworkEvent.objects.get()
        self.assertIn("Degraded to Healthy", event.message)
        self.assertEqual(format_discord_payload(event)["embeds"][0]["color"], 0x12B886)
        notify.assert_called_once_with(event)

    @patch("core.speedtest_tracker.notify_event")
    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_same_result_is_not_processed_twice(self, latest, notify):
        self.config.speedtest_last_result_id = "12"
        self.config.speedtest_last_healthy = True
        self.config.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )
        latest.return_value = (self.result(12, True), False)

        result = check_speedtest_health_change()

        self.assertEqual(result["status"], "already_checked")
        notify.assert_not_called()
        self.assertFalse(NetworkEvent.objects.exists())

    @patch("core.speedtest_tracker.notify_event")
    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_new_result_with_same_health_only_advances_baseline(self, latest, notify):
        self.config.speedtest_last_result_id = "12"
        self.config.speedtest_last_healthy = True
        self.config.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )
        latest.return_value = (self.result(13, True), False)

        result = check_speedtest_health_change()

        self.assertEqual(result, {"status": "unchanged", "result_id": "13"})
        self.config.refresh_from_db()
        self.assertEqual(self.config.speedtest_last_result_id, "13")
        self.assertTrue(self.config.speedtest_last_healthy)
        notify.assert_not_called()
        self.assertFalse(NetworkEvent.objects.exists())

    @patch("core.speedtest_tracker.notify_event")
    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_unscored_result_does_not_replace_baseline(self, latest, notify):
        self.config.speedtest_last_result_id = "12"
        self.config.speedtest_last_healthy = True
        self.config.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )
        latest.return_value = (self.result(13, None), False)

        result = check_speedtest_health_change()

        self.assertEqual(result, {"status": "unscored", "result_id": "13"})
        self.config.refresh_from_db()
        self.assertEqual(self.config.speedtest_last_result_id, "12")
        self.assertTrue(self.config.speedtest_last_healthy)
        notify.assert_not_called()

    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_connection_failure_does_not_change_state(self, latest):
        self.config.speedtest_last_result_id = "12"
        self.config.speedtest_last_healthy = True
        self.config.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )
        latest.side_effect = SpeedtestTrackerError("unavailable")

        result = check_speedtest_health_change()

        self.assertEqual(result["status"], "unavailable")
        self.config.refresh_from_db()
        self.assertEqual(self.config.speedtest_last_result_id, "12")
        self.assertTrue(self.config.speedtest_last_healthy)

    @patch("core.speedtest_tracker.latest_speedtest_result")
    def test_disabled_rule_does_not_fetch_result(self, latest):
        self.config.notify_speedtest_changes = False
        self.config.save(update_fields=["notify_speedtest_changes"])

        self.assertEqual(check_speedtest_health_change()["status"], "disabled")
        latest.assert_not_called()

    def test_notification_rule_allows_speedtest_event(self):
        event = NetworkEvent.objects.create(
            event_type=NetworkEvent.EventType.SPEEDTEST_HEALTH_CHANGED,
            message="Speedtest changed from Healthy to Degraded.",
        )

        self.assertTrue(notification_event_allowed(event, self.config))

    def test_settings_change_resets_saved_baseline(self):
        self.config.notify_speedtest_changes = False
        self.config.speedtest_last_result_id = "12"
        self.config.speedtest_last_healthy = True
        self.config.save()
        serializer = AppSettingsSerializer(
            self.config,
            data={"notify_speedtest_changes": True},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.config.refresh_from_db()
        self.assertTrue(self.config.notify_speedtest_changes)
        self.assertEqual(self.config.speedtest_last_result_id, "")
        self.assertIsNone(self.config.speedtest_last_healthy)
