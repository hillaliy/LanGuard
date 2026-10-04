from unittest.mock import Mock, patch

from django.contrib.auth.models import User
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

class NotificationApiTests(TestCase):
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

    def test_notification_test_endpoint_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "discord",
                "discord_webhook": "https://discord.example/webhook",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    @patch("core.views.notifications.send_discord_test")
    def test_notification_test_endpoint_sends_discord_without_history(self, send_test):
        delivery_count = NotificationDelivery.objects.count()
        event_count = NetworkEvent.objects.count()

        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "discord",
                "discord_webhook": "https://discord.example/webhook",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["channel"], "discord")
        send_test.assert_called_once_with("https://discord.example/webhook")
        self.assertEqual(NotificationDelivery.objects.count(), delivery_count)
        self.assertEqual(NetworkEvent.objects.count(), event_count)

    @patch("core.views.notifications.send_discord_test")
    def test_notification_test_endpoint_uses_saved_discord_webhook(self, send_test):
        config = AppSettings.load()
        config.discord_webhook = "https://discord.example/saved-webhook"
        config.save(update_fields=["discord_webhook"])

        response = self.client.post(
            "/api/v1/notifications/test/",
            {"channel": "discord"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        send_test.assert_called_once_with("https://discord.example/saved-webhook")

    @patch("core.views.notifications.send_telegram_test")
    def test_notification_test_endpoint_sends_telegram(self, send_test):
        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "telegram",
                "telegram_api_url": "https://relay.example/telegram/",
                "telegram_token": "bot-token",
                "telegram_user_id": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        send_test.assert_called_once_with(
            "bot-token",
            "123456",
            "https://relay.example/telegram",
        )

    @patch("core.views.notifications.send_telegram_test")
    def test_notification_test_endpoint_uses_saved_telegram_token(self, send_test):
        config = AppSettings.load()
        config.telegram_api_url = "http://telegram-relay:8081"
        config.telegram_token = "saved-bot-token"
        config.save(update_fields=["telegram_api_url", "telegram_token"])

        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "telegram",
                "telegram_user_id": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        send_test.assert_called_once_with(
            "saved-bot-token",
            "123456",
            "http://telegram-relay:8081",
        )

    @patch("core.views.notifications.send_ntfy_test")
    def test_notification_test_endpoint_sends_ntfy(self, send_test):
        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "ntfy",
                "ntfy_server_url": "https://ntfy.example",
                "ntfy_topic": "languard",
                "ntfy_priority": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["channel"], "ntfy")
        send_test.assert_called_once_with("https://ntfy.example", "languard", 5)

    def test_notification_test_endpoint_rejects_incomplete_ntfy_settings(self):
        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "ntfy",
                "ntfy_server_url": "https://ntfy.example",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ntfy_topic", response.data)

    @patch("core.views.notifications.send_webhook_test")
    def test_notification_test_endpoint_sends_webhook(self, send_test):
        config = AppSettings.load()
        config.webhook_secret = "saved-secret"
        config.save(update_fields=["webhook_secret"])
        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "webhook",
                "webhook_url": "https://automation.example/webhook/languard",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["channel"], "webhook")
        send_test.assert_called_once_with(
            "https://automation.example/webhook/languard",
            "saved-secret",
        )

    def test_notification_test_endpoint_rejects_missing_webhook_url(self):
        response = self.client.post(
            "/api/v1/notifications/test/",
            {"channel": "webhook"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("webhook_url", response.data)

    def test_notification_test_endpoint_rejects_incomplete_credentials(self):
        response = self.client.post(
            "/api/v1/notifications/test/",
            {"channel": "telegram", "telegram_token": "bot-token"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("telegram", response.data)

    @patch("core.views.notifications.send_discord_test")
    def test_notification_test_endpoint_sanitizes_upstream_error(self, send_test):
        upstream_response = Mock(status_code=401)
        send_test.side_effect = requests.HTTPError(
            "https://discord.example/secret-webhook failed",
            response=upstream_response,
        )

        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "discord",
                "discord_webhook": "https://discord.example/secret-webhook",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.data["detail"],
            "Discord rejected the test notification. HTTP 401.",
        )
        self.assertNotIn("secret-webhook", response.data["detail"])

    @patch("core.views.notifications.send_telegram_test")
    def test_notification_test_endpoint_explains_missing_telegram_chat(self, send_test):
        upstream_response = Mock(status_code=400)
        send_test.side_effect = requests.HTTPError(
            "Telegram request failed with a secret bot token",
            response=upstream_response,
        )

        response = self.client.post(
            "/api/v1/notifications/test/",
            {
                "channel": "telegram",
                "telegram_token": "secret-bot-token",
                "telegram_user_id": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.data["detail"],
            (
                "Telegram rejected the chat. Check the chat ID and send /start "
                "to the bot before testing. HTTP 400."
            ),
        )
        self.assertNotIn("secret-bot-token", response.data["detail"])
