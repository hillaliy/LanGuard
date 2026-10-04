
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import (
    Device,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)

class ActivityApiTests(TestCase):
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

    def test_events_endpoint_returns_events(self):
        response = self.client.get("/api/v1/events/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["id"], self.event.id)
        self.assertTrue(response.data["data"][0]["created_at"].endswith("Z"))
        self.assertEqual(response.data["pagination"]["count"], 1)

    def test_events_endpoint_filters_by_type_and_notified(self):
        NetworkEvent.objects.create(
            scan_run=self.scan_run,
            device=self.device,
            event_type=NetworkEvent.EventType.PORT_OPENED,
            message="Laptop opened tcp/22",
            notified=True,
        )

        response = self.client.get(
            "/api/v1/events/",
            {"event_type": "port_opened", "notified": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["event_type"], "port_opened")

    def test_events_endpoint_rejects_bad_limit(self):
        response = self.client.get("/api/v1/events/", {"limit": "bad"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("limit", response.data)

    def test_notifications_endpoint_filters_by_status(self):
        response = self.client.get("/api/v1/notifications/", {"status": "failed"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["id"], self.delivery.id)
        self.assertTrue(response.data["data"][0]["created_at"].endswith("Z"))
