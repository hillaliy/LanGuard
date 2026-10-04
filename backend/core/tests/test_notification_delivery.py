from datetime import datetime, timedelta, timezone as datetime_timezone
import hashlib
import hmac
import importlib
import json
import socket
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.cache import cache
from django.db import DatabaseError, OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
import requests
from rest_framework.test import APIClient

from backend.settings import include_internal_hosts, validate_production_settings
from ..datetime_utils import utc_isoformat
from ..management.commands.run_scheduler import load_scan_schedule
from ..models import (
    AppSettings,
    Device,
    DeviceIPAddressAssignment,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
    UserAccess,
)
from ..notifications import (
    format_discord_payload,
    format_webhook_payload,
    notify_event,
    quiet_hours_active,
    retry_failed_notifications,
    send_discord_test,
    send_ntfy_test,
    send_telegram,
    send_telegram_test,
    send_webhook_test,
)
from ..port_guidance import PORT_CATALOG, port_guidance
from ..serializers.devices import device_attention_reasons, device_identity
from ..views.inventory import parse_inventory_datetime
from ..versioning import check_for_version_update, is_newer_version
from ..scanning.discovery import (
    MDNS_SERVICE_HOSTNAME_CACHE,
    detect_web_interface,
    dns_encode_name,
    dns_ptr_names,
    dns_server_reverse_hostname,
    get_hostname,
    hostname_from_device_description,
    llmnr_reverse_hostname,
    mdns_multicast_responses,
    mdns_query_responses,
    mdns_reverse_hostname,
    mdns_service_hostname,
    mdns_service_hostname_map,
    mdns_service_hostnames_from_response,
    mdns_service_hostnames_from_responses,
    mdns_service_types_from_response,
    ssdp_hostname_from_response,
    ssdp_metadata_from_response,
    web_interface_candidates,
)
from ..scanning.events import create_event
from ..scanning.identity import (
    clean_hostname,
    guess_device_identity,
    mismatched_default_haa_hostname,
    preferred_vendor,
)
from ..scanning.lifecycle import (
    STALE_SCAN_ERROR,
    ScanAlreadyRunning,
    active_scan_run,
    claim_scan_run,
    scan_failure_diagnostics,
)
from ..scanning.network import (
    default_gateway_from_proc_route,
    discover_devices,
    local_scanner_interface,
)
from ..scanning.orchestration import scan
from ..scanning.ports import normalize_scan_ports, sync_device_ports
from ..scanning.presence import (
    clear_stale_gateways,
    mark_missing_devices_offline,
)
from ..scanning.ranges import validate_ip_range, validate_ip_ranges
from ..scanning.reconciliation import sync_discovered_device
from ..scanning.vendor import ManufVendorDB, manuf_vendor

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

    def test_quiet_hours_only_apply_on_selected_day(self):
        config = AppSettings(
            time_zone="UTC",
            notification_quiet_hours_enabled=True,
            notification_quiet_hours_start="09:00",
            notification_quiet_hours_end="17:00",
            notification_quiet_hours_days=["mon"],
        )

        monday = datetime(2026, 8, 24, 12, 0, tzinfo=datetime_timezone.utc)
        tuesday = datetime(2026, 8, 25, 12, 0, tzinfo=datetime_timezone.utc)

        self.assertTrue(quiet_hours_active(config, now=monday))
        self.assertFalse(quiet_hours_active(config, now=tuesday))

    def test_overnight_quiet_hours_use_the_starting_day(self):
        config = AppSettings(
            time_zone="UTC",
            notification_quiet_hours_enabled=True,
            notification_quiet_hours_start="22:00",
            notification_quiet_hours_end="07:00",
            notification_quiet_hours_days=["mon"],
        )

        monday_night = datetime(2026, 8, 24, 23, 0, tzinfo=datetime_timezone.utc)
        tuesday_morning = datetime(2026, 8, 25, 2, 0, tzinfo=datetime_timezone.utc)
        tuesday_night = datetime(2026, 8, 25, 23, 0, tzinfo=datetime_timezone.utc)

        self.assertTrue(quiet_hours_active(config, now=monday_night))
        self.assertTrue(quiet_hours_active(config, now=tuesday_morning))
        self.assertFalse(quiet_hours_active(config, now=tuesday_night))

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

    @override_settings(DISCORD_ICON_URL="https://example.com/languard.png?v=1.1.4")
    def test_discord_payload_preserves_cache_busting_icon_url(self):
        payload = format_discord_payload(self.event)
        embed = payload["embeds"][0]

        self.assertEqual(payload["avatar_url"], "https://example.com/languard.png?v=1.1.4")
        self.assertEqual(embed["author"]["icon_url"], "https://example.com/languard.png?v=1.1.4")
        self.assertEqual(embed["thumbnail"]["url"], "https://example.com/languard.png?v=1.1.4")

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_version_update_notification_supports_system_events(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            notify_version_updates=True,
            discord_enabled=True,
            discord_webhook="https://discord.example/webhook",
        )
        event = NetworkEvent.objects.create(
            event_type=NetworkEvent.EventType.VERSION_AVAILABLE,
            message="LanGuard 1.1.0 is available.",
            metadata={"latest_version": "1.1.0"},
        )

        deliveries = notify_event(event)

        self.assertEqual(len(deliveries), 1)
        event.refresh_from_db()
        self.assertTrue(event.notified)
        discord_payload = post.call_args.kwargs["json"]
        self.assertEqual(
            discord_payload["embeds"][0]["title"],
            "LanGuard: Version available",
        )
        self.assertEqual(discord_payload["embeds"][0]["color"], 0x228BE6)
        self.assertNotIn("fields", discord_payload["embeds"][0])
        webhook_payload = format_webhook_payload(event)
        self.assertEqual(webhook_payload["kind"], "system_event")
        self.assertIsNone(webhook_payload["device"])

    @override_settings(
        DISCORD_ICON_URL="https://example.com/languard.png",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_discord_test_uses_dedicated_payload(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        send_discord_test("https://discord.example/webhook")

        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://discord.example/webhook")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["username"], "LanGuard")
        self.assertEqual(payload["embeds"][0]["title"], "LanGuard: Test notification")
        self.assertIn("channel is working", payload["embeds"][0]["description"])

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_telegram_test_uses_supplied_credentials(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        send_telegram_test("bot-token", "123456")

        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://api.telegram.org/botbot-token/sendMessage",
        )
        self.assertEqual(post.call_args.kwargs["json"]["chat_id"], "123456")
        self.assertIn(
            "Test notification",
            post.call_args.kwargs["json"]["text"],
        )

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_telegram_test_uses_custom_api_base_url(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        send_telegram_test(
            "bot-token",
            "123456",
            "http://telegram-relay:8081/telegram/",
        )

        self.assertEqual(
            post.call_args.args[0],
            "http://telegram-relay:8081/telegram/botbot-token/sendMessage",
        )

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_telegram_delivery_uses_saved_api_base_url(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        config = AppSettings(
            telegram_api_url="https://relay.example/telegram",
            telegram_token="bot-token",
            telegram_user_id="123456",
        )

        send_telegram(self.event, config)

        self.assertEqual(
            post.call_args.args[0],
            "https://relay.example/telegram/botbot-token/sendMessage",
        )

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_ntfy_test_uses_configured_topic_and_priority(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        send_ntfy_test("https://ntfy.example", "languard", 4)

        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://ntfy.example")
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "topic": "languard",
                "title": "LanGuard: Test notification",
                "message": (
                    "This is a test notification from LanGuard. "
                    "Your notification channel is working."
                ),
                "priority": 4,
                "tags": ["white_check_mark"],
            },
        )

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_ntfy_notification_delivery_is_recorded(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            ntfy_enabled=True,
            ntfy_server_url="https://ntfy.example",
            ntfy_topic="languard",
            ntfy_priority=4,
        )

        deliveries = notify_event(self.event)

        self.assertEqual(len(deliveries), 1)
        delivery = NotificationDelivery.objects.get(event=self.event)
        self.assertEqual(delivery.channel, NotificationDelivery.Channel.NTFY)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(post.call_args.args[0], "https://ntfy.example")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["topic"], "languard")
        self.assertEqual(payload["title"], "LanGuard: New device")
        self.assertEqual(payload["priority"], 4)
        self.assertIn("Device: Camera", payload["message"])

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_webhook_test_uses_structured_payload(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        send_webhook_test(
            "https://automation.example/webhook/languard",
            "shared-secret",
        )

        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://automation.example/webhook/languard",
        )
        body = post.call_args.kwargs["data"]
        payload = json.loads(body)
        self.assertEqual(payload["source"], "languard")
        self.assertEqual(payload["kind"], "test")
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("channel is working", payload["message"])
        self.assertTrue(payload["created_at"].endswith("Z"))
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-LanGuard-Delivery"], payload["delivery_id"])
        expected_signature = hmac.new(
            b"shared-secret",
            f"{headers['X-LanGuard-Timestamp']}.".encode("utf-8") + body,
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(
            headers["X-LanGuard-Signature"],
            f"sha256={expected_signature}",
        )

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_webhook_notification_delivery_is_recorded(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            webhook_enabled=True,
            webhook_url="https://automation.example/webhook/languard",
            webhook_secret="shared-secret",
        )

        deliveries = notify_event(self.event)

        self.assertEqual(len(deliveries), 1)
        delivery = NotificationDelivery.objects.get(event=self.event)
        self.assertEqual(delivery.channel, NotificationDelivery.Channel.WEBHOOK)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        payload = json.loads(post.call_args.kwargs["data"])
        self.assertEqual(
            payload,
            format_webhook_payload(self.event, delivery_id=delivery.id),
        )
        self.assertEqual(payload["delivery_id"], delivery.id)
        self.assertEqual(payload["source"], "languard")
        self.assertEqual(payload["kind"], "network_event")
        self.assertEqual(payload["event"]["type"], "new_device")
        self.assertEqual(payload["device"]["mac"], "11:22:33:44:55:66")
        self.assertEqual(payload["device"]["ip"], "192.168.1.50")
        self.assertIn("X-LanGuard-Signature", post.call_args.kwargs["headers"])

    @override_settings(NOTIFICATION_TIMEOUT=1)
    @patch("core.notifications.requests.post")
    def test_webhook_without_secret_is_delivered_unsigned(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            webhook_enabled=True,
            webhook_url="https://automation.example/webhook/languard",
        )

        notify_event(self.event)

        self.assertNotIn(
            "X-LanGuard-Signature",
            post.call_args.kwargs["headers"],
        )

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
    def test_visitor_presence_rule_is_quiet_by_default(self, post):
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notify_device_online=True,
        )
        self.device.known = True
        self.device.is_visitor = True
        self.device.save(update_fields=["known", "is_visitor"])
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Visitor came online",
        )

        deliveries = notify_event(event)

        self.assertEqual(deliveries, [])
        post.assert_not_called()
        event.refresh_from_db()
        self.assertEqual(
            event.metadata["notification_skipped"],
            "visitor_presence_default",
        )

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_visitor_always_preference_enables_presence_notification(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notify_device_online=False,
        )
        self.device.known = True
        self.device.is_visitor = True
        self.device.online_notification_preference = Device.NotificationPreference.ALWAYS
        self.device.save(
            update_fields=["known", "is_visitor", "online_notification_preference"]
        )
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Visitor came online",
        )

        deliveries = notify_event(event)

        self.assertEqual(len(deliveries), 1)
        post.assert_called_once()

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_device_always_preference_overrides_disabled_global_rule(self, post):
        post.return_value = Mock(raise_for_status=Mock())
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notify_device_online=False,
        )
        self.device.online_notification_preference = Device.NotificationPreference.ALWAYS
        self.device.save(update_fields=["online_notification_preference"])
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Camera came online",
        )

        deliveries = notify_event(event)

        self.assertEqual(len(deliveries), 1)
        post.assert_called_once()

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_device_never_preference_overrides_enabled_global_rule(self, post):
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notify_device_offline=True,
        )
        self.device.offline_notification_preference = Device.NotificationPreference.NEVER
        self.device.save(update_fields=["offline_notification_preference"])
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            message="Camera went offline",
        )

        deliveries = notify_event(event)

        self.assertEqual(deliveries, [])
        post.assert_not_called()
        event.refresh_from_db()
        self.assertEqual(
            event.metadata["notification_skipped"],
            "device_notification_disabled",
        )

    @override_settings(
        NOTIFICATIONS_ENABLED=True,
        DISCORD_WEBHOOK="https://discord.example/webhook",
        TELEGRAM_TOKEN="",
        TELEGRAM_USERID="",
        NOTIFICATION_TIMEOUT=1,
    )
    @patch("core.notifications.requests.post")
    def test_device_always_preference_still_obeys_quiet_hours(self, post):
        AppSettings.objects.create(
            discord_webhook="https://discord.example/webhook",
            notification_quiet_hours_enabled=True,
            notification_quiet_hours_start="00:00",
            notification_quiet_hours_end="00:00",
        )
        self.device.online_notification_preference = Device.NotificationPreference.ALWAYS
        self.device.save(update_fields=["online_notification_preference"])
        event = NetworkEvent.objects.create(
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Camera came online",
        )

        deliveries = notify_event(event)

        self.assertEqual(deliveries, [])
        post.assert_not_called()
        event.refresh_from_db()
        self.assertEqual(event.metadata["notification_skipped"], "quiet_hours")

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
        self.assertNotIn("temporary failure", delivery.error)

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
    def test_failed_notification_without_event_is_not_retried(self, post):
        NotificationDelivery.objects.create(
            event=None,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.FAILED,
            attempts=1,
        )

        retried = retry_failed_notifications()

        self.assertEqual(retried, [])
        post.assert_not_called()

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=3)
    @patch("core.notifications.requests.post")
    def test_failed_delivery_is_skipped_after_channel_is_disabled(self, post):
        AppSettings.objects.create(
            webhook_enabled=False,
            webhook_url="https://automation.example/webhook/languard",
        )
        delivery = NotificationDelivery.objects.create(
            event=self.event,
            channel=NotificationDelivery.Channel.WEBHOOK,
            status=NotificationDelivery.Status.FAILED,
            attempts=1,
        )

        retried = retry_failed_notifications()

        delivery.refresh_from_db()
        self.assertEqual(retried, [])
        self.assertEqual(delivery.status, NotificationDelivery.Status.SKIPPED)
        post.assert_not_called()

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

    @patch("core.scanning.events.notify_event")
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

    @patch("core.scanning.events.notify_event")
    def test_known_device_presence_event_uses_notification_rules(self, notify_event_mock):
        device = Device.objects.create(
            name="Known Camera",
            ip="192.168.1.50",
            mac="11:22:33:44:55:66",
            known=True,
        )

        event = create_event(
            NetworkEvent.EventType.DEVICE_OFFLINE,
            device,
            "Known Camera went offline",
            scan_run=self.scan_run,
        )

        notify_event_mock.assert_called_once_with(event)

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
