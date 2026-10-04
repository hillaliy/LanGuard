import hashlib
import ipaddress
import json
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..datetime_utils import utc_isoformat
from ..models import (
    AdGuardUnmatchedClient,
    AppSettings,
    Device,
    DetailedPortScan,
    DeviceDNSActivity,
    DevicePort,
    DockerContainer,
    DockerHost,
    NetworkEvent,
    NotificationDelivery,
    QUIET_HOURS_DAY_KEYS,
    ScanRun,
    default_scan_range_label,
)
from ..port_guidance import port_attention, port_guidance
from ..user_messages import stored_error_message


from .common import UTCDateTimeField

class NotificationDeliverySerializer(serializers.ModelSerializer):
    created_at = UTCDateTimeField(read_only=True)
    sent_at = UTCDateTimeField(read_only=True)
    channel_display = serializers.CharField(
        source="get_channel_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    error = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField)
    def get_error(self, obj):
        return stored_error_message("notification", obj.error)

    class Meta:
        model = NotificationDelivery
        fields = "__all__"


class NotificationTestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=(
            NotificationDelivery.Channel.DISCORD,
            NotificationDelivery.Channel.TELEGRAM,
            NotificationDelivery.Channel.NTFY,
            NotificationDelivery.Channel.WEBHOOK,
        )
    )
    discord_webhook = serializers.URLField(
        required=False,
        allow_blank=True,
        write_only=True,
    )
    webhook_url = serializers.URLField(required=False, allow_blank=True, max_length=2048)
    webhook_secret = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        write_only=True,
    )
    telegram_token = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        write_only=True,
    )
    telegram_api_url = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=2048,
        trim_whitespace=True,
    )
    telegram_user_id = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )
    ntfy_server_url = serializers.URLField(
        required=False,
        allow_blank=True,
        max_length=2048,
    )
    ntfy_topic = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    ntfy_priority = serializers.ChoiceField(
        required=False,
        choices=(1, 2, 3, 4, 5),
        default=3,
    )

    def validate_telegram_api_url(self, value):
        from ..notifications import normalize_telegram_api_url

        try:
            return normalize_telegram_api_url(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        channel = attrs["channel"]
        if channel == NotificationDelivery.Channel.DISCORD:
            saved_webhook = AppSettings.load().discord_webhook
            if not (attrs.get("discord_webhook", "").strip() or saved_webhook):
                raise serializers.ValidationError(
                    {"discord_webhook": "Enter a Discord webhook URL."}
                )
        elif channel == NotificationDelivery.Channel.TELEGRAM:
            saved_token = AppSettings.load().telegram_token
            if (
                not (attrs.get("telegram_token", "").strip() or saved_token)
                or not attrs.get("telegram_user_id", "").strip()
            ):
                raise serializers.ValidationError(
                    {
                        "telegram": (
                            "Enter both a Telegram bot token and user ID."
                        )
                    }
                )
        elif channel == NotificationDelivery.Channel.NTFY:
            if not attrs.get("ntfy_server_url", "").strip():
                raise serializers.ValidationError(
                    {"ntfy_server_url": "Enter an ntfy server URL."}
                )
            if not attrs.get("ntfy_topic", "").strip():
                raise serializers.ValidationError(
                    {"ntfy_topic": "Enter an ntfy topic."}
                )
        elif channel == NotificationDelivery.Channel.WEBHOOK:
            if not attrs.get("webhook_url", "").strip():
                raise serializers.ValidationError(
                    {"webhook_url": "Enter a webhook URL."}
                )
        return attrs


