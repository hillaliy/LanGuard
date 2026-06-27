from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
import requests
from rest_framework.test import APIClient

from backend.settings import validate_production_settings
from .models import Device, DevicePort, NetworkEvent, NotificationDelivery, ScanRun
from .notifications import notify_event, retry_failed_notifications
from .scan import normalize_scan_ports, sync_device_ports, validate_ip_range


class ProductionSettingsTests(SimpleTestCase):
    def test_development_allows_local_defaults(self):
        validate_production_settings(
            "development",
            "unsafe-dev-secret-key",
            True,
            ["localhost", "127.0.0.1"],
        )

    def test_production_rejects_unsafe_defaults(self):
        with self.assertRaises(ImproperlyConfigured) as context:
            validate_production_settings(
                "production",
                "change-me",
                True,
                ["localhost", "127.0.0.1"],
            )

        message = str(context.exception)
        self.assertIn("SECRET_KEY", message)
        self.assertIn("DEBUG", message)
        self.assertIn("LAN IP", message)

    def test_production_accepts_strong_local_network_config(self):
        validate_production_settings(
            "production",
            "a-strong-production-secret-key-value",
            False,
            ["languard.local", "192.168.1.10"],
        )


@override_settings(NOTIFICATIONS_ENABLED=False)
class PortEventTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="Router",
            ip="192.168.1.1",
            mac="aa:bb:cc:dd:ee:ff",
            vendor="Example",
        )
        self.scan_run = ScanRun.objects.create(ip_range="192.168.1.0/24")

    def test_open_and_closed_ports_create_events(self):
        opened = sync_device_ports(
            self.device,
            [{"port": 80, "protocol": "tcp", "service": "http"}],
            scan_run=self.scan_run,
        )

        self.assertEqual(opened["ports_opened"], 1)
        self.assertEqual(opened["ports_closed"], 0)
        self.assertTrue(DevicePort.objects.get(device=self.device, port=80).open)
        self.assertTrue(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.PORT_OPENED,
                device=self.device,
                scan_run=self.scan_run,
            ).exists()
        )

        closed = sync_device_ports(self.device, [], scan_run=self.scan_run)

        self.assertEqual(closed["ports_opened"], 0)
        self.assertEqual(closed["ports_closed"], 1)
        self.assertFalse(DevicePort.objects.get(device=self.device, port=80).open)
        self.assertTrue(
            NetworkEvent.objects.filter(
                event_type=NetworkEvent.EventType.PORT_CLOSED,
                device=self.device,
                scan_run=self.scan_run,
            ).exists()
        )


class NotificationTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="Camera",
            ip="192.168.1.50",
            mac="11:22:33:44:55:66",
        )
        self.event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.NEW_DEVICE,
            message="Found new device Camera at 192.168.1.50",
        )

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_discord_notification_delivery_is_recorded(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        deliveries = notify_event(self.event)

        self.assertEqual(len(deliveries), 1)
        delivery = NotificationDelivery.objects.get(event=self.event)
        self.assertEqual(delivery.channel, NotificationDelivery.Channel.DISCORD)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.attempts, 1)
        self.event.refresh_from_db()
        self.assertTrue(self.event.notified)

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
        NOTIFICATION_MAX_ATTEMPTS=3,
    )
    @patch("core.notifications.requests.post")
    def test_failed_notification_can_be_retried(self, post):
        post.side_effect = [
            requests.RequestException("temporary failure"),
            Mock(raise_for_status=Mock()),
        ]

        notify_event(self.event)
        delivery = NotificationDelivery.objects.get(event=self.event)
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(delivery.attempts, 1)

        retried = retry_failed_notifications()
        delivery.refresh_from_db()

        self.assertEqual(retried, [delivery])
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.attempts, 2)
        self.event.refresh_from_db()
        self.assertTrue(self.event.notified)

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
        NOTIFICATION_MAX_ATTEMPTS=3,
    )
    @patch("core.notifications.requests.post")
    def test_retry_notifications_command(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        NotificationDelivery.objects.create(
            event=self.event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.FAILED,
            attempts=1,
        )

        call_command("retry_notifications")

        delivery = NotificationDelivery.objects.get(event=self.event)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.attempts, 2)


@override_settings(NOTIFICATIONS_ENABLED=False)
class ScanApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="password")
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

    def test_scan_endpoints_require_authentication(self):
        client = APIClient()

        response = client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 401)

    def test_scan_status_endpoint_returns_latest_scan_and_counters(self):
        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertEqual(response.data["counters"]["all_devices"], 1)
        self.assertEqual(response.data["counters"]["unnotified_events"], 1)

    def test_scan_runs_endpoint_returns_history(self):
        response = self.client.get("/api/v1/scan/runs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["id"], self.scan_run.id)
        self.assertEqual(response.data["pagination"]["count"], 1)

    def test_scan_runs_endpoint_filters_by_status(self):
        ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.FAILED,
            error="failed",
        )

        response = self.client.get("/api/v1/scan/runs/", {"status": "failed"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["status"], ScanRun.Status.FAILED)

    def test_events_endpoint_returns_events(self):
        response = self.client.get("/api/v1/events/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["id"], self.event.id)
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

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_scan_now_rejects_public_ranges(self):
        response = self.client.post(
            "/api/v1/scan/",
            {"ip_range": "8.8.8.0/24"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ip_range", response.data)

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_validate_ip_range_rejects_large_ranges(self):
        with self.assertRaises(ValueError):
            validate_ip_range("192.168.0.0/16")

    @override_settings(PORT_SCAN_MAX_PORTS=2)
    def test_normalize_scan_ports_enforces_port_count_limit(self):
        with self.assertRaises(ValueError):
            normalize_scan_ports([22, 80, 443])
