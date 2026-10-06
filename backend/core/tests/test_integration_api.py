from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
import requests
from rest_framework.test import APIClient

from ..models import (
    AppSettings,
    Device,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)

class IntegrationApiTests(TestCase):
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

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_latest_result_is_normalized_and_cached(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "id": 42,
                    "download_bits": 500_000_000,
                    "upload_bits": 100_000_000,
                    "download_bits_human": "500 Mbps",
                    "upload_bits_human": "100 Mbps",
                    "ping": 8.4,
                    "healthy": True,
                    "status": "completed",
                    "created_at": "2026-09-02T06:00:00Z",
                    "data": {"packetLoss": 0},
                }
            ),
        )
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        first = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")
        second = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["data"]["download_mbps"], 500.0)
        self.assertEqual(first.data["data"]["upload_mbps"], 100.0)
        self.assertEqual(first.data["data"]["packet_loss_percent"], 0.0)
        self.assertTrue(first.data["integration"]["available"])
        self.assertFalse(first.data["integration"]["cached"])
        self.assertTrue(second.data["integration"]["cached"])
        self.assertNotIn("private-api-token", str(first.data))
        get.assert_called_once()
        self.assertEqual(
            get.call_args.kwargs["params"],
            {"filter[status]": "completed"},
        )

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_normalizes_nested_ookla_measurements(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "id": 43,
                    "healthy": True,
                    "status": "completed",
                    "data": {
                        "download": {"bandwidth": 62_500_000},
                        "upload": {"bandwidth": 12_500_000},
                        "ping": {"latency": 8.4},
                        "packetLoss": 0,
                        "timestamp": "2026-10-05T16:00:00Z",
                    },
                }
            ),
        )
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        response = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["download_mbps"], 500.0)
        self.assertEqual(response.data["data"]["upload_mbps"], 100.0)
        self.assertEqual(response.data["data"]["ping_ms"], 8.4)
        self.assertEqual(response.data["data"]["packet_loss_percent"], 0.0)
        self.assertEqual(response.data["data"]["tested_at"], "2026-10-05T16:00:00Z")

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_incomplete_result_is_unavailable_and_not_cached(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "id": 44,
                    "status": "completed",
                    "data": {"timestamp": "2026-10-05T16:05:00Z"},
                }
            ),
        )
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        first = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")
        second = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")

        self.assertIsNone(first.data["data"])
        self.assertFalse(first.data["integration"]["available"])
        self.assertIsNone(second.data["data"])
        self.assertEqual(get.call_count, 2)

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_refresh_bypasses_cache(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "id": 1,
                    "status": "completed",
                    "download": 500,
                    "upload": 100,
                    "ping": 8,
                }
            ),
        )
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        self.client.get("/api/v1/integrations/speedtest-tracker/latest/")
        response = self.client.get(
            "/api/v1/integrations/speedtest-tracker/latest/",
            {"refresh": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["integration"]["cached"])
        self.assertEqual(get.call_count, 2)

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_unavailable_does_not_fail_dashboard_request(self, get):
        cache.clear()
        get.side_effect = requests.Timeout("private upstream detail")
        config = AppSettings.load()
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://192.168.1.5:8080"
        config.speedtest_tracker_api_token = "private-api-token"
        config.save()

        response = self.client.get("/api/v1/integrations/speedtest-tracker/latest/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["data"])
        self.assertFalse(response.data["integration"]["available"])
        self.assertNotIn("private", str(response.data))

    @patch("core.integrations.speedtest_tracker.requests.get")
    def test_speedtest_tracker_connection_test_uses_saved_token(self, get):
        cache.clear()
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "id": 1,
                    "status": "completed",
                    "download": 500,
                    "upload": 100,
                    "ping": 8,
                }
            ),
        )
        config = AppSettings.load()
        config.speedtest_tracker_api_token = "saved-api-token"
        config.save(update_fields=["speedtest_tracker_api_token"])

        response = self.client.post(
            "/api/v1/integrations/speedtest-tracker/test/",
            {"url": "http://192.168.1.5:8080"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["notification"]["title"], "Speedtest Tracker connected")
        self.assertNotIn("saved-api-token", str(response.data))

    def test_speedtest_tracker_connection_test_requires_admin_user(self):
        regular_user = User.objects.create_user(username="speed-viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/integrations/speedtest-tracker/test/",
            {
                "url": "http://192.168.1.5:8080",
                "api_token": "private-api-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_speedtest_tracker_latest_requires_authentication(self):
        anonymous_client = APIClient()

        response = anonymous_client.get(
            "/api/v1/integrations/speedtest-tracker/latest/"
        )

        self.assertIn(response.status_code, {401, 403})
