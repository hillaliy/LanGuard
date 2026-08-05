from datetime import timedelta
import socket
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
from .datetime_utils import utc_isoformat
from .models import (
    AppSettings,
    Device,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)
from .notifications import notify_event, retry_failed_notifications
from .scan import (
    clear_stale_gateways,
    create_event,
    clean_hostname,
    default_gateway_from_proc_route,
    discover_devices,
    guess_device_identity,
    get_hostname,
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


class HostnameResolutionTests(SimpleTestCase):
    def test_clean_hostname_normalizes_dns_name(self):
        self.assertEqual(clean_hostname("living-room-device.local."), "living room device")

    def test_clean_hostname_returns_blank_when_unavailable(self):
        self.assertEqual(clean_hostname(""), "")

    @patch("core.scan.socket.gethostbyaddr", side_effect=socket.herror)
    def test_get_hostname_returns_blank_when_reverse_dns_is_unavailable(self, _):
        self.assertEqual(get_hostname("192.168.1.10"), "")


class ApiDocsAccessTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_openapi_schema_is_public(self):
        response = self.client.get("/api/schema/")

        self.assertEqual(response.status_code, 200)

    def test_swagger_ui_is_public(self):
        response = self.client.get("/api/schema/swagger/")

        self.assertEqual(response.status_code, 200)

    def test_redoc_is_public(self):
        response = self.client.get("/api/schema/redoc/")

        self.assertEqual(response.status_code, 200)


class VersionStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(
        APP_VERSION="1.0.2",
        LATEST_VERSION_URL="https://example.test/package.json",
        VERSION_CHECK_TIMEOUT=1,
    )
    @patch("core.views.urllib.request.urlopen")
    def test_version_endpoint_returns_latest_public_version(self, urlopen):
        response_mock = Mock()
        response_mock.read.return_value = b'{"version": "1.0.3"}'
        urlopen.return_value.__enter__.return_value = response_mock

        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["current_version"], "1.0.2")
        self.assertEqual(response.data["data"]["latest_version"], "1.0.3")
        self.assertEqual(response.data["data"]["check_interval_seconds"], 21600)

    @override_settings(APP_VERSION="1.0.2", LATEST_VERSION_URL="")
    def test_version_endpoint_uses_saved_check_interval(self):
        AppSettings.objects.create(version_check_interval=1800)

        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["check_interval_seconds"], 1800)

    @override_settings(APP_VERSION="1.0.2", LATEST_VERSION_URL="")
    def test_version_endpoint_falls_back_without_latest_source(self):
        response = self.client.get("/api/v1/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["current_version"], "1.0.2")
        self.assertIsNone(response.data["data"]["latest_version"])


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_first_registered_user_becomes_admin(self):
        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "admin",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_staff"])
        self.assertTrue(response.data["is_superuser"])
        user = User.objects.get(username="admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_registration_is_closed_after_first_user_exists(self):
        User.objects.create_user(username="admin", password="password")

        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "viewer",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="viewer").exists())

    def test_setup_status_reports_registration_open(self):
        response = self.client.get("/api/v1/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["registration_open"])

    def test_setup_status_reports_registration_closed_after_user_exists(self):
        User.objects.create_user(username="admin", password="password")

        response = self.client.get("/api/v1/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["registration_open"])

    def test_login_returns_role_flags(self):
        User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
            is_superuser=True,
        )

        response = self.client.post(
            "/api/v1/login/",
            {"username": "admin", "password": "password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])
        self.assertTrue(response.data["is_superuser"])


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
            scan_run=ScanRun.objects.create(ip_range="192.168.1.0/24"),
        )
        device.refresh_from_db()
        self.assertTrue(device.online)
        self.assertEqual(device.missed_scans, 1)
        self.assertEqual(device.status, Device.Status.RECENTLY_SEEN)
        self.assertEqual(device.status_source, Device.StatusSource.RECENT)

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
    @patch("core.scan.scan_open_ports")
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
    @patch("core.scan.scan_open_ports")
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
    @patch("core.scan.scapy.sr1")
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

        self.assertEqual(identity["name"], "TP-Link")
        self.assertEqual(identity["icon"], "router")

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
    @patch("core.scan.get_hostname")
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

        self.assertEqual(identity["name"], "Foxconn")

    def test_guess_device_identity_uses_vendor_profile_name(self):
        identity = guess_device_identity(
            hostname="Device",
            vendor="Espressif Inc.",
            mac="aa:bb:cc:dd:ee:ff",
        )

        self.assertEqual(identity["name"], "Espressif IoT device")

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

    def test_guess_device_identity_detects_aqara_hub(self):
        identity = guess_device_identity(
            hostname="gateway",
            vendor="Aqara",
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
            vendor="GD Midea Air-Conditioning Equipment Co.,Ltd.",
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
                hostname="kids ipad",
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
        DISCORD_ICON_URL="https://example.com/languard.png",
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
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["username"], "LanGuard")
        self.assertEqual(payload["avatar_url"], "https://example.com/languard.png")
        self.assertNotIn("content", payload)
        embed = payload["embeds"][0]
        self.assertEqual(embed["title"], "LanGuard: New device")
        self.assertEqual(embed["description"], "Found new device Camera at 192.168.1.50")
        self.assertEqual(embed["color"], 0xE03131)
        self.assertEqual(embed["author"]["icon_url"], "https://example.com/languard.png")
        self.assertEqual(embed["thumbnail"]["url"], "https://example.com/languard.png")
        self.assertTrue(embed["timestamp"].endswith("Z"))
        self.assertEqual(
            {field["name"]: field["value"] for field in embed["fields"]},
            {
                "Device": "Camera",
                "IP": "192.168.1.50",
                "MAC": "11:22:33:44:55:66",
            },
        )
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
    )
    @patch("core.notifications.requests.post")
    def test_enabled_device_online_rule_sends_delivery(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notify_device_online=True,
        )
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Camera came online",
        )

        deliveries = notify_event(event)

        self.assertEqual(len(deliveries), 1)
        post.assert_called_once()
        event.refresh_from_db()
        self.assertTrue(event.notified)

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_quiet_hours_skip_external_delivery(self, post):
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notification_quiet_hours_enabled=True,
            notification_quiet_hours_start="00:00",
            notification_quiet_hours_end="00:00",
        )

        deliveries = notify_event(self.event)

        self.assertEqual(deliveries, [])
        post.assert_not_called()
        self.event.refresh_from_db()
        self.assertTrue(self.event.notified)
        self.assertEqual(self.event.metadata["notification_skipped"], "quiet_hours")

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

    def test_scan_endpoints_require_authentication(self):
        client = APIClient()

        response = client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 401)

    def test_users_endpoint_lists_users(self):
        response = self.client.get("/api/v1/users/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["username"], "admin")
        self.assertNotIn("password", response.data["data"][0])

    def test_users_endpoint_regular_user_lists_only_self(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/users/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["username"], "viewer")

    def test_users_endpoint_regular_user_updates_self_only(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.put(
            f"/api/v1/users/?id={regular_user.id}",
            {
                "username": "viewer-updated",
                "first_name": "yossi",
                "last_name": "user",
                "is_staff": True,
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        regular_user.refresh_from_db()
        self.assertEqual(regular_user.username, "viewer-updated")
        self.assertEqual(regular_user.first_name, "Yossi")
        self.assertEqual(regular_user.last_name, "User")
        self.assertFalse(regular_user.is_staff)
        self.assertTrue(regular_user.is_active)

    def test_users_endpoint_regular_user_cannot_edit_other_users(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.put(
            f"/api/v1/users/?id={self.user.id}",
            {"username": "admin-changed"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "admin")

    def test_users_endpoint_regular_user_cannot_create_or_delete_users(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        create_response = regular_client.post(
            "/api/v1/users/",
            {
                "username": "other",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )
        delete_response = regular_client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_users_endpoint_creates_user(self):
        response = self.client.post(
            "/api/v1/users/",
            {
                "username": "viewer",
                "password": "secret-password",
                "password_confirm": "secret-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="viewer").exists())
        self.assertEqual(response.data["data"]["username"], "viewer")

    def test_users_endpoint_updates_user(self):
        user = User.objects.create_user(username="viewer", password="old-password")

        response = self.client.put(
            f"/api/v1/users/?id={user.id}",
            {
                "username": "viewer-updated",
                "first_name": "view",
                "last_name": "er",
                "password": "new-password",
                "password_confirm": "new-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "viewer-updated")
        self.assertEqual(user.first_name, "View")
        self.assertEqual(user.last_name, "Er")
        self.assertTrue(user.check_password("new-password"))

    def test_users_endpoint_deletes_user(self):
        user = User.objects.create_user(username="viewer", password="password")

        response = self.client.delete(f"/api/v1/users/?id={user.id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=user.id).exists())

    def test_users_endpoint_rejects_deleting_last_user(self):
        response = self.client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_users_endpoint_rejects_deleting_last_admin(self):
        User.objects.create_user(username="viewer", password="password")

        response = self.client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_users_endpoint_rejects_deleting_last_inactive_admin(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        User.objects.create_user(username="viewer", password="password")

        response = self.client.delete(f"/api/v1/users/?id={self.user.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_users_endpoint_rejects_demoting_last_admin(self):
        response = self.client.put(
            f"/api/v1/users/?id={self.user.id}",
            {"is_staff": False},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

    def test_settings_endpoint_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/settings/")

        self.assertEqual(response.status_code, 403)

    def test_settings_endpoint_updates_scan_and_notification_settings(self):
        response = self.client.put(
            "/api/v1/settings/",
            {
                "ip_range": "192.168.1.0/24",
                "scan_interval": 15,
                "time_zone": "Asia/Jerusalem",
                "version_check_interval": 3600,
                "discord_enabled": False,
                "telegram_enabled": True,
                "notify_new_devices": True,
                "notify_device_online": True,
                "notify_device_offline": True,
                "notify_port_changes": True,
                "notification_quiet_hours_enabled": True,
                "notification_quiet_hours_start": "23:00",
                "notification_quiet_hours_end": "06:30",
                "discord_webhook": "https://discord.example/webhook",
                "telegram_token": "token",
                "telegram_user_id": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = AppSettings.load()
        self.assertEqual(config.ip_range, "192.168.1.0/24")
        self.assertEqual(config.scan_interval, 15)
        self.assertEqual(config.time_zone, "Asia/Jerusalem")
        self.assertEqual(config.version_check_interval, 3600)
        self.assertFalse(config.discord_enabled)
        self.assertTrue(config.telegram_enabled)
        self.assertTrue(config.notify_new_devices)
        self.assertTrue(config.notify_device_online)
        self.assertTrue(config.notify_device_offline)
        self.assertTrue(config.notify_port_changes)
        self.assertTrue(config.notification_quiet_hours_enabled)
        self.assertEqual(config.notification_quiet_hours_start, "23:00")
        self.assertEqual(config.notification_quiet_hours_end, "06:30")
        self.assertEqual(config.discord_webhook, "https://discord.example/webhook")
        self.assertEqual(config.telegram_token, "token")
        self.assertEqual(config.telegram_user_id, "123")
        self.assertEqual(
            response.data["data"]["discord_webhook"],
            "https://discord.example/webhook",
        )
        self.assertEqual(response.data["data"]["telegram_token"], "token")
        self.assertEqual(response.data["data"]["telegram_user_id"], "123")
        self.assertFalse(response.data["data"]["discord_enabled"])
        self.assertTrue(response.data["data"]["telegram_enabled"])
        self.assertTrue(response.data["data"]["discord_configured"])
        self.assertEqual(response.data["data"]["version_check_interval"], 3600)
        self.assertTrue(response.data["data"]["notify_device_online"])
        self.assertTrue(response.data["data"]["notify_device_offline"])
        self.assertTrue(response.data["data"]["notify_port_changes"])
        self.assertTrue(response.data["data"]["notification_quiet_hours_enabled"])
        self.assertEqual(response.data["data"]["notification_quiet_hours_start"], "23:00")
        self.assertEqual(response.data["data"]["notification_quiet_hours_end"], "06:30")

    def test_settings_endpoint_rejects_short_version_check_interval(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"version_check_interval": 30},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("version_check_interval", response.data)

    def test_settings_endpoint_rejects_bad_quiet_hours(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"notification_quiet_hours_start": "23:00:00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("notification_quiet_hours_start", response.data)

    @override_settings(SCAN_MAX_HOSTS=256, SCAN_ALLOW_PUBLIC_RANGES=False)
    def test_settings_endpoint_rejects_unsafe_scan_range(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"ip_range": "8.8.8.0/24"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ip_range", response.data)

    def test_settings_endpoint_rejects_bad_timezone(self):
        response = self.client.put(
            "/api/v1/settings/",
            {"time_zone": "Bad/Timezone"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("time_zone", response.data)

    def test_scan_status_endpoint_returns_latest_scan_and_counters(self):
        self.scan_run.started_at = timezone.now() - timedelta(minutes=2)
        self.scan_run.finished_at = timezone.now()
        self.scan_run.save(update_fields=["started_at", "finished_at"])
        Device.objects.create(
            name="Stale phone",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
            online=False,
            status=Device.Status.ONLINE,
        )
        Device.objects.create(
            name="Offline camera",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
            online=True,
            status=Device.Status.OFFLINE,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertEqual(response.data["counters"]["all_devices"], 3)
        self.assertEqual(response.data["counters"]["online_devices"], 2)
        self.assertEqual(response.data["counters"]["offline_devices"], 1)
        self.assertEqual(response.data["counters"]["unnotified_events"], 1)
        self.assertEqual(response.data["time_zone"], "UTC")
        self.assertFalse(response.data["visibility"]["is_scanning"])
        self.assertEqual(response.data["visibility"]["current_range"], "192.168.1.0/24")
        self.assertTrue(response.data["data"]["started_at"].endswith("Z"))
        self.assertTrue(response.data["data"]["finished_at"].endswith("Z"))
        self.assertTrue(response.data["visibility"]["started_at"].endswith("Z"))
        self.assertTrue(response.data["visibility"]["finished_at"].endswith("Z"))
        self.assertGreaterEqual(response.data["visibility"]["duration_seconds"], 119)

    def test_scan_status_endpoint_returns_active_scan_visibility(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.2.0/24",
            status=ScanRun.Status.RUNNING,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_scan"]["id"], running_scan.id)
        self.assertTrue(response.data["visibility"]["is_scanning"])
        self.assertEqual(response.data["visibility"]["current_range"], "192.168.2.0/24")
        self.assertTrue(response.data["active_scan"]["started_at"].endswith("Z"))
        self.assertTrue(response.data["visibility"]["started_at"].endswith("Z"))

    def test_scan_status_endpoint_keeps_latest_completed_scan_during_running_scan(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
        )

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertEqual(response.data["active_scan"]["id"], running_scan.id)

    def test_scan_status_endpoint_finishes_superseded_running_scan(self):
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
            started_at=timezone.now() - timedelta(minutes=30),
        )
        self.scan_run.started_at = timezone.now() - timedelta(minutes=5)
        self.scan_run.finished_at = timezone.now() - timedelta(minutes=1)
        self.scan_run.save(update_fields=["started_at", "finished_at"])

        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.scan_run.id)
        self.assertIsNone(response.data["active_scan"])
        self.assertFalse(response.data["visibility"]["is_scanning"])
        self.assertEqual(
            response.data["visibility"]["finished_at"],
            utc_isoformat(self.scan_run.finished_at),
        )
        running_scan.refresh_from_db()
        self.assertEqual(running_scan.status, ScanRun.Status.FAILED)
        self.assertEqual(
            running_scan.error,
            "Scan was superseded by a newer completed scan.",
        )

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

    def test_device_endpoint_filters_by_display_status(self):
        Device.objects.create(
            name="Status online but stale boolean",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
            online=False,
            status=Device.Status.ONLINE,
        )
        offline_device = Device.objects.create(
            name="Offline camera",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
            online=True,
            status=Device.Status.OFFLINE,
        )

        response = self.client.get("/api/v1/device/", {"status": Device.Status.OFFLINE})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["data"][0]["id"], offline_device.id)
        self.assertEqual(response.data["data"][0]["status"], Device.Status.OFFLINE)

    def test_device_endpoint_rejects_invalid_status_filter(self):
        response = self.client.get("/api/v1/device/", {"status": "gone"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

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

    def test_device_endpoint_returns_utc_datetime_strings(self):
        self.device.last_status_check = timezone.now()
        self.device.last_port_scan = timezone.now()
        self.device.save(update_fields=["last_status_check", "last_port_scan"])
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertTrue(device["firstseen"].endswith("Z"))
        self.assertTrue(device["lastseen"].endswith("Z"))
        self.assertTrue(device["last_status_check"].endswith("Z"))
        self.assertTrue(device["last_port_scan"].endswith("Z"))
        self.assertTrue(device["open_ports"][0]["firstseen"].endswith("Z"))
        self.assertTrue(device["open_ports"][0]["lastseen"].endswith("Z"))

    def test_device_endpoint_includes_low_risk_badge_data(self):
        self.device.known = True
        self.device.vendor = "Apple"
        self.device.save()

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "low")
        self.assertEqual(device["risk_score"], 0)
        self.assertEqual(device["risk_reasons"], [])

    def test_device_endpoint_flags_unknown_device_with_risky_ports(self):
        self.device.known = False
        self.device.vendor = ""
        self.device.save()
        DevicePort.objects.create(device=self.device, port=22, protocol="tcp", open=True)
        DevicePort.objects.create(device=self.device, port=445, protocol="tcp", open=True)

        response = self.client.get("/api/v1/device/")

        self.assertEqual(response.status_code, 200)
        device = response.data["data"][0]
        self.assertEqual(device["risk_level"], "high")
        self.assertGreaterEqual(device["risk_score"], 5)
        self.assertIn("New unknown device", device["risk_reasons"])
        self.assertTrue(
            any("Risky open ports" in reason for reason in device["risk_reasons"])
        )

    def test_device_endpoint_rejects_too_large_page_size(self):
        response = self.client.get("/api/v1/device/", {"limit": 101})

        self.assertEqual(response.status_code, 400)
        self.assertIn("limit", response.data)

    def test_device_inventory_export_requires_admin(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/devices/export/")

        self.assertEqual(response.status_code, 403)

    def test_device_inventory_export_returns_shared_format(self):
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)

        response = self.client.get("/api/v1/devices/export/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["format"], "languard-device-inventory")
        exported_device = response.json()["devices"][0]
        self.assertEqual(exported_device["name"], "Laptop")
        self.assertEqual(exported_device["mac"], "aa:aa:aa:aa:aa:aa")
        self.assertEqual(exported_device["open_ports"], [80])
        self.assertTrue(exported_device["first_seen"].endswith("Z"))

    def test_device_inventory_import_updates_existing_device_by_mac(self):
        self.device.firstseen = timezone.now() - timedelta(days=1)
        self.device.save(update_fields=["firstseen"])

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Living Room TV",
                        "ip": "192.168.1.50",
                        "mac": "aa:aa:aa:aa:aa:aa",
                        "vendor": "Apple",
                        "icon": "tv",
                        "known": True,
                        "is_gateway": False,
                        "status": Device.Status.ONLINE,
                        "open_ports": [80, "443"],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["created"], 0)
        self.assertEqual(response.data["data"]["updated"], 1)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Living Room TV")
        self.assertEqual(self.device.ip, "192.168.1.50")
        self.assertEqual(self.device.vendor, "Apple")
        self.assertEqual(self.device.icon, "tv")
        self.assertTrue(self.device.known)
        self.assertEqual(
            list(self.device.ports.filter(open=True).values_list("port", flat=True)),
            [80, 443],
        )

    def test_device_inventory_import_creates_new_device(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Camera",
                        "ip": "192.168.1.60",
                        "mac": "bb:bb:bb:bb:bb:bb",
                        "vendor": "Reolink",
                        "icon": "security-camera",
                        "known": True,
                        "open_ports": [554],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["created"], 1)
        imported = Device.objects.get(mac="bb:bb:bb:bb:bb:bb")
        self.assertEqual(imported.name, "Camera")
        self.assertEqual(imported.ports.get().port, 554)

    def test_device_inventory_import_accepts_macos_export_shape(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "exported_at": 790000000,
                "devices": [
                    {
                        "name": "Guest Sensor",
                        "ip": "192.168.1.70",
                        "mac": "AA-BB-CC-DD-EE-FF",
                        "vendor": "Example",
                        "hostname": "sensor.local",
                        "icon": "thermometer.medium",
                        "secondary_icon": "light.strip.2",
                        "role": "sensor",
                        "room": "Kitchen",
                        "known": True,
                        "is_gateway": False,
                        "status": "online",
                        "open_ports": [80, "443", 80],
                        "first_seen": 790000000,
                        "last_seen": 790000060,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        imported = Device.objects.get(mac="aa:bb:cc:dd:ee:ff")
        self.assertEqual(imported.icon, "thermostat")
        self.assertEqual(imported.secondary_icon, "led-strip")
        self.assertEqual(imported.role, "sensor")
        self.assertEqual(imported.room, "Kitchen")
        self.assertEqual(
            list(imported.ports.filter(open=True).values_list("port", flat=True)),
            [80, 443],
        )

    def test_scan_runs_endpoint_returns_history(self):
        response = self.client.get("/api/v1/scan/runs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["id"], self.scan_run.id)
        self.assertTrue(response.data["data"][0]["started_at"].endswith("Z"))
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
    def test_scan_now_uses_saved_default_range(self, scan_mock):
        AppSettings.objects.create(ip_range="192.168.1.0/24", scan_interval=10)
        scan_mock.return_value = self.scan_run

        response = self.client.post("/api/v1/scan/", {}, format="json")

        self.assertEqual(response.status_code, 202)
        scan_mock.assert_called_once_with("192.168.1.0/24")

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
