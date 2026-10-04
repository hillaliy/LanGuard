from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import (
    Device,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)

class DevicePresenceApiTests(TestCase):
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

    def test_device_availability_uses_presence_events_across_selected_period(self):
        now = timezone.now()
        device = Device.objects.create(
            name="Availability device",
            ip="192.168.1.30",
            mac="bb:bb:bb:bb:bb:bb",
            firstseen=now - timedelta(days=20),
        )
        NetworkEvent.objects.create(
            device=device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Device came online",
            created_at=now - timedelta(days=10),
        )
        NetworkEvent.objects.create(
            device=device,
            event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            message="Device went offline",
            created_at=now - timedelta(days=3),
        )
        NetworkEvent.objects.create(
            device=device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Device came online",
            created_at=now - timedelta(days=1),
        )

        response = self.client.get(
            "/api/v1/device/availability/",
            {"device": device.id, "period": "week"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["period"], "week")
        self.assertEqual(
            [segment["status"] for segment in data["segments"]],
            ["online", "offline", "online"],
        )
        self.assertAlmostEqual(data["availability_percent"], 71.4, delta=0.1)
        self.assertEqual(data["coverage_percent"], 100.0)
        self.assertEqual(data["status_changes"], 2)
        self.assertAlmostEqual(data["online_seconds"], 5 * 86400, delta=2)

    def test_device_availability_reports_missing_history_as_unknown(self):
        now = timezone.now()
        device = Device.objects.create(
            name="Partially tracked device",
            ip="192.168.1.31",
            mac="cc:cc:cc:cc:cc:cc",
            firstseen=now - timedelta(days=20),
        )
        NetworkEvent.objects.create(
            device=device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Device came online",
            created_at=now - timedelta(days=1),
        )

        response = self.client.get(
            "/api/v1/device/availability/",
            {"device": device.id, "period": "week"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(
            [segment["status"] for segment in data["segments"]],
            ["unknown", "online"],
        )
        self.assertEqual(data["availability_percent"], 100.0)
        self.assertAlmostEqual(data["coverage_percent"], 14.3, delta=0.1)

    def test_device_availability_validates_period_and_authentication(self):
        response = self.client.get(
            "/api/v1/device/availability/",
            {"device": self.device.id, "period": "decade"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("period", response.data)

        unauthenticated_client = APIClient()
        response = unauthenticated_client.get(
            "/api/v1/device/availability/",
            {"device": self.device.id, "period": "week"},
        )
        self.assertEqual(response.status_code, 401)

    def test_device_availability_day_clips_to_last_24_hours(self):
        self.device.events.all().delete()
        now = timezone.now()
        for hours, event_type in (
            (30, NetworkEvent.EventType.DEVICE_ONLINE),
            (6, NetworkEvent.EventType.DEVICE_OFFLINE),
            (2, NetworkEvent.EventType.DEVICE_ONLINE),
        ):
            NetworkEvent.objects.create(
                device=self.device, event_type=event_type,
                message="Presence", created_at=now - timedelta(hours=hours),
            )
        with patch("core.views.devices.timezone.now", return_value=now):
            response = self.client.get("/api/v1/device/availability/", {"device": self.device.id, "period": "day"})
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["period"], "day")
        self.assertEqual(data["online_seconds"], 20 * 3600)
        self.assertEqual(data["offline_seconds"], 4 * 3600)
        self.assertEqual(data["coverage_percent"], 100)
        self.assertEqual(data["availability_percent"], 83.3)
        self.assertEqual(data["status_changes"], 2)
        self.assertEqual(sum(segment["duration_seconds"] for segment in data["segments"]), 86400)

    def test_device_availability_day_without_history_is_unknown(self):
        self.device.events.all().delete()
        response = self.client.get("/api/v1/device/availability/", {"device": self.device.id, "period": "day"})
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertIsNone(data["availability_percent"])
        self.assertEqual(data["coverage_percent"], 0)
        self.assertEqual(data["segments"][0]["status"], "unknown")

    def test_device_endpoint_flags_regular_device_offline_for_over_week(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.lastseen = timezone.now() - timedelta(days=8)
        self.device.save(
            update_fields=["known", "vendor", "online", "status", "lastseen"]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["risk_level"], "low")
        self.assertEqual(device["attention_reasons"], ["Offline for over 7 days"])
        self.assertTrue(device["needs_attention"])

    def test_device_endpoint_does_not_flag_recently_offline_device(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.lastseen = timezone.now() - timedelta(days=6)
        self.device.save(
            update_fields=["known", "vendor", "online", "status", "lastseen"]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["attention_reasons"], [])
        self.assertFalse(device["needs_attention"])

    def test_automatic_presence_allows_portable_device_three_weeks(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.role = "phone"
        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.lastseen = timezone.now() - timedelta(days=14)
        self.device.save(
            update_fields=["known", "vendor", "role", "online", "status", "lastseen"]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["presence_expectation"], "automatic")
        self.assertEqual(device["offline_attention_effective_days"], 21)
        self.assertEqual(device["attention_reasons"], [])
        self.assertFalse(device["needs_attention"])

        self.device.lastseen = timezone.now() - timedelta(days=22)
        self.device.save(update_fields=["lastseen"])
        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["attention_reasons"], ["Offline for over 21 days"])
        self.assertTrue(device["needs_attention"])

    def test_custom_presence_threshold_controls_offline_attention(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.presence_expectation = Device.PresenceExpectation.OCCASIONAL
        self.device.offline_attention_after_days = 14
        self.device.lastseen = timezone.now() - timedelta(days=15)
        self.device.save(
            update_fields=[
                "known",
                "vendor",
                "online",
                "status",
                "presence_expectation",
                "offline_attention_after_days",
                "lastseen",
            ]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["offline_attention_effective_days"], 14)
        self.assertEqual(device["attention_reasons"], ["Offline for over 14 days"])

    def test_device_can_disable_offline_attention(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.presence_expectation = Device.PresenceExpectation.NEVER
        self.device.lastseen = timezone.now() - timedelta(days=365)
        self.device.save(
            update_fields=[
                "known",
                "vendor",
                "online",
                "status",
                "presence_expectation",
                "lastseen",
            ]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertIsNone(device["offline_attention_effective_days"])
        self.assertEqual(device["attention_reasons"], [])
        self.assertFalse(device["needs_attention"])

    def test_device_endpoint_does_not_flag_offline_visitor_after_week(self):
        self.device.known = True
        self.device.is_visitor = True
        self.device.vendor = "Apple"
        self.device.online = False
        self.device.status = Device.Status.OFFLINE
        self.device.lastseen = timezone.now() - timedelta(days=8)
        self.device.save(
            update_fields=[
                "known",
                "is_visitor",
                "vendor",
                "online",
                "status",
                "lastseen",
            ]
        )

        device = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]

        self.assertEqual(device["attention_reasons"], [])
        self.assertFalse(device["needs_attention"])

    def test_device_rejects_presence_threshold_outside_supported_range(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {
                "presence_expectation": Device.PresenceExpectation.ALWAYS,
                "offline_attention_after_days": 3651,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("offline_attention_after_days", response.data["info"])
