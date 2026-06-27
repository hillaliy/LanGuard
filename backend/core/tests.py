from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
import requests
from rest_framework.test import APIClient

from backend.settings import validate_production_settings
from .models import Device, DevicePort, NetworkEvent, NotificationDelivery, ScanRun
from .notifications import notify_event, retry_failed_notifications
from .scan import (
    create_event,
    discover_devices,
    guess_device_identity,
    mark_missing_devices_offline,
    normalize_scan_ports,
    sync_discovered_device,
    sync_device_ports,
    validate_ip_range,
)


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


@override_settings(NOTIFICATIONS_ENABLED=False)
class ScanStabilityTests(TestCase):
    def scan_element(self, ip, mac):
        return (None, SimpleNamespace(psrc=ip, hwsrc=mac))

    @override_settings(SCAN_ARP_RETRIES=2, SCAN_ARP_TIMEOUT=2)
    @patch("core.scan.scapy.srp")
    def test_discover_devices_retries_and_deduplicates_by_mac(self, srp):
        first = self.scan_element("192.168.1.10", "AA:BB:CC:DD:EE:01")
        second = self.scan_element("192.168.1.11", "AA:BB:CC:DD:EE:02")
        duplicate = self.scan_element("192.168.1.10", "aa:bb:cc:dd:ee:01")
        srp.side_effect = [([first], None), ([duplicate, second], None)]

        devices = discover_devices("192.168.1.0/24")

        self.assertEqual(len(devices), 2)
        self.assertEqual(srp.call_count, 2)

    @override_settings(SCAN_OFFLINE_AFTER_MISSES=3)
    def test_missing_device_is_not_marked_offline_until_grace_limit(self):
        device = Device.objects.create(
            name="Router",
            ip="192.168.1.1",
            mac="aa:bb:cc:dd:ee:ff",
            online=True,
        )

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 1)

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 2)

        mark_missing_devices_offline(
            [],
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )
        device.refresh_from_db()
        self.assertFalse(device.online)
        self.assertEqual(device.missed_scans, 3)
        self.assertTrue(
            NetworkEvent.objects.filter(
                device=device,
                event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            ).exists()
        )

    @override_settings(PORT_SCAN_ENABLED=True, PORT_SCAN_INTERVAL=30)
    @patch("core.scan.scan_open_ports")
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
    @patch("core.scan.scan_open_ports")
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
            hostname="apple-tv-livingroom",
            vendor="Apple, Inc.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["name"], "apple-tv-livingroom")
        self.assertEqual(identity["icon"], "streamer")

    def test_guess_device_identity_uses_vendor_fallback_name(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="TP-Link Technologies Co., Ltd.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["name"], "TP-Link device EEFF")
        self.assertEqual(identity["icon"], "router")

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch("core.scan.get_hostname")
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
            vendor="Aqara",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "shutter")

    def test_guess_device_identity_detects_air_conditioner(self):
        identity = guess_device_identity(
            hostname="bedroom-air-conditioner",
            vendor="GD Midea Air-Conditioning Equipment Co.,Ltd.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["icon"], "air-conditioner")


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
    )
    @patch("core.notifications.requests.post")
    def test_non_enabled_event_type_is_recorded_without_delivery(self, post):
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Camera came online",
        )

        deliveries = notify_event(event)

        self.assertEqual(deliveries, [])
        post.assert_not_called()
        event.refresh_from_db()
        self.assertTrue(event.notified)
        self.assertEqual(event.metadata["notification_skipped"], "event_type_not_enabled")

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


@override_settings(NOTIFICATIONS_ENABLED=True)
class ScanNotificationTests(TestCase):
    def setUp(self):
        self.scan_run = ScanRun.objects.create(ip_range="192.168.1.0/24")

    @patch("core.scan.notify_event")
    def test_known_device_events_are_recorded_without_external_notification(
        self, notify_event_mock
    ):
        device = Device.objects.create(
            name="Known Camera",
            ip="192.168.1.50",
            mac="11:22:33:44:55:66",
            known=True,
        )

        sync_device_ports(
            device,
            [{"port": 80, "protocol": "tcp", "service": "http"}],
            scan_run=self.scan_run,
        )

        event = NetworkEvent.objects.get(
            event_type=NetworkEvent.EventType.PORT_OPENED,
            device=device,
        )
        self.assertTrue(event.notified)
        self.assertEqual(event.metadata["notification_skipped"], "known_device")
        notify_event_mock.assert_not_called()

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_unknown_port_events_are_recorded_without_external_notification(
        self, post
    ):
        device = Device.objects.create(
            name="New Camera",
            ip="192.168.1.51",
            mac="22:33:44:55:66:77",
            known=False,
        )

        sync_device_ports(
            device,
            [{"port": 80, "protocol": "tcp", "service": "http"}],
            scan_run=self.scan_run,
        )

        event = NetworkEvent.objects.get(
            event_type=NetworkEvent.EventType.PORT_OPENED,
            device=device,
        )
        self.assertTrue(event.notified)
        self.assertEqual(event.metadata["notification_skipped"], "event_type_not_enabled")
        post.assert_not_called()

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_unknown_new_device_events_send_external_notification(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        device = Device.objects.create(
            name="New Camera",
            ip="192.168.1.51",
            mac="22:33:44:55:66:77",
            known=False,
        )

        event = create_event(
            NetworkEvent.EventType.NEW_DEVICE,
            device=device,
            scan_run=self.scan_run,
            message=f"Found new device {device.name} at {device.ip}",
        )

        delivery = NotificationDelivery.objects.get(event=event)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        post.assert_called_once()


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

    def test_scan_status_endpoint_keeps_latest_completed_scan_during_running_scan(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertEqual(response.data["active_scan"]["id"], running_scan.id)

    def test_device_endpoint_paginates_devices(self):
        Device.objects.create(
            name="Tablet",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
        )
        Device.objects.create(
            name="Phone",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
        )

        response = self.client.get("/api/v1/device/", {"limit": 2, "offset": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["pagination"]["count"], 3)
        self.assertEqual(response.data["pagination"]["limit"], 2)
        self.assertEqual(response.data["pagination"]["offset"], 0)
        self.assertEqual(response.data["pagination"]["next_offset"], 2)

    def test_device_endpoint_sorts_by_name(self):
        Device.objects.create(
            name="Access point",
            ip="192.168.1.30",
            mac="bb:bb:bb:bb:bb:bb",
        )
        Device.objects.create(
            name="Camera",
            ip="192.168.1.40",
            mac="cc:cc:cc:cc:cc:cc",
        )

        response = self.client.get("/api/v1/device/", {"ordering": "name"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [device["name"] for device in response.data["data"]],
            ["Access point", "Camera", "Laptop"],
        )

    def test_device_endpoint_sorts_by_ip_naturally(self):
        Device.objects.create(
            name="Low IP",
            ip="192.168.1.2",
            mac="bb:bb:bb:bb:bb:bb",
        )
        Device.objects.create(
            name="High IP",
            ip="192.168.1.100",
            mac="cc:cc:cc:cc:cc:cc",
        )

        response = self.client.get("/api/v1/device/", {"ordering": "ip"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [device["ip"] for device in response.data["data"]],
            ["192.168.1.2", "192.168.1.20", "192.168.1.100"],
        )

    def test_device_endpoint_counters_include_current_open_ports(self):
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)
        DevicePort.objects.create(
            device=self.device,
            port=443,
            protocol="tcp",
            open=False,
        )

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["counters"]["open_ports"], 1)

    def test_device_endpoint_rejects_too_large_page_size(self):
        response = self.client.get("/api/v1/device/", {"limit": 101})

        self.assertEqual(response.status_code, 400)
        self.assertIn("limit", response.data)

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
    @patch("core.views.scan")
    def test_scan_now_returns_json_when_scanner_lacks_permissions(self, scan_mock):
        scan_mock.side_effect = Exception(
            "Permission denied: could not open /dev/bpf0. Make sure to be running Scapy as root ! (sudo)"
        )

        response = self.client.post(
            "/api/v1/scan/",
            {"ip_range": "192.168.1.0/24"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "Error")
        self.assertIn("packet-capture permissions", response.data["info"])

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_validate_ip_range_rejects_large_ranges(self):
        with self.assertRaises(ValueError):
            validate_ip_range("192.168.0.0/16")

    @override_settings(PORT_SCAN_MAX_PORTS=2)
    def test_normalize_scan_ports_enforces_port_count_limit(self):
        with self.assertRaises(ValueError):
            normalize_scan_ports([22, 80, 443])
