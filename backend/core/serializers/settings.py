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
from .home_map import validate_home_map_layout_value

class AppSettingsSerializer(serializers.ModelSerializer):
    updated_at = UTCDateTimeField(read_only=True)
    adguard_last_sync_at = UTCDateTimeField(read_only=True)
    pihole_last_sync_at = UTCDateTimeField(read_only=True)
    scan_max_hosts = serializers.SerializerMethodField()
    discord_configured = serializers.SerializerMethodField()
    telegram_configured = serializers.SerializerMethodField()
    ntfy_configured = serializers.SerializerMethodField()
    webhook_configured = serializers.SerializerMethodField()
    webhook_signature_configured = serializers.SerializerMethodField()
    adguard_configured = serializers.SerializerMethodField()
    pihole_configured = serializers.SerializerMethodField()
    speedtest_tracker_configured = serializers.SerializerMethodField()
    homebox_configured = serializers.SerializerMethodField()
    homebox_api_token = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=512)

    @extend_schema_field(serializers.BooleanField)
    def get_homebox_configured(self, obj):
        return bool(obj.homebox_url and obj.homebox_api_token)

    def validate_homebox_url(self, value):
        from ..integrations.homebox import HomeBoxError, normalize_url
        if not value:
            return ""
        try:
            return normalize_url(value)
        except HomeBoxError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    discord_webhook = serializers.URLField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    adguard_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
    )
    pihole_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
    )
    telegram_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
    )
    telegram_api_url = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=2048,
        trim_whitespace=True,
    )
    webhook_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
    )
    speedtest_tracker_api_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=512,
        trim_whitespace=True,
    )
    clear_webhook_secret = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )
    adguard_last_error = serializers.SerializerMethodField()
    pihole_last_error = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField)
    def get_adguard_last_error(self, obj):
        return stored_error_message("adguard", obj.adguard_last_error)

    @extend_schema_field(serializers.CharField)
    def get_pihole_last_error(self, obj):
        return stored_error_message("pihole", obj.pihole_last_error)

    class Meta:
        model = AppSettings
        fields = (
            "ip_range",
            "scan_ranges",
            "scan_range_labels",
            "scan_max_hosts",
            "scan_interval",
            "time_zone",
            "version_check_interval",
            "notifications_enabled",
            "discord_enabled",
            "discord_webhook",
            "discord_configured",
            "telegram_enabled",
            "telegram_api_url",
            "telegram_token",
            "telegram_user_id",
            "telegram_configured",
            "ntfy_enabled",
            "ntfy_server_url",
            "ntfy_topic",
            "ntfy_priority",
            "ntfy_configured",
            "webhook_enabled",
            "webhook_url",
            "webhook_secret",
            "clear_webhook_secret",
            "webhook_configured",
            "webhook_signature_configured",
            "notify_new_devices",
            "notify_device_online",
            "notify_device_offline",
            "notify_port_changes",
            "notify_version_updates",
            "notify_speedtest_changes",
            "notification_quiet_hours_enabled",
            "notification_quiet_hours_start",
            "notification_quiet_hours_end",
            "notification_quiet_hours_days",
            "activity_cleanup_retention_days",
            "adguard_enabled",
            "adguard_url",
            "adguard_username",
            "adguard_password",
            "adguard_configured",
            "adguard_sync_interval",
            "adguard_retention_days",
            "adguard_last_sync_at",
            "adguard_last_error",
            "pihole_enabled",
            "pihole_url",
            "pihole_password",
            "pihole_configured",
            "pihole_sync_interval",
            "pihole_retention_days",
            "pihole_last_sync_at",
            "pihole_last_error",
            "speedtest_tracker_enabled",
            "homebox_enabled",
            "homebox_url",
            "homebox_api_token",
            "homebox_configured",
            "speedtest_tracker_url",
            "speedtest_tracker_api_token",
            "speedtest_tracker_configured",
            "home_map_layout",
            "updated_at",
        )
        extra_kwargs = {
            "telegram_user_id": {"required": False, "allow_blank": True},
            "ntfy_server_url": {"required": False, "allow_blank": True},
            "ntfy_topic": {"required": False, "allow_blank": True},
            "webhook_url": {"required": False, "allow_blank": True},
            "adguard_url": {"required": False, "allow_blank": True},
            "adguard_username": {"required": False, "allow_blank": True},
            "adguard_last_sync_at": {"read_only": True},
            "adguard_last_error": {"read_only": True},
            "pihole_url": {"required": False, "allow_blank": True},
            "pihole_last_sync_at": {"read_only": True},
            "pihole_last_error": {"read_only": True},
            "speedtest_tracker_url": {"required": False, "allow_blank": True},
            "updated_at": {"read_only": True},
        }

    def validate_telegram_api_url(self, value):
        from ..notifications import normalize_telegram_api_url

        try:
            return normalize_telegram_api_url(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    @extend_schema_field(serializers.IntegerField)
    def get_scan_max_hosts(self, obj):
        return settings.SCAN_MAX_HOSTS

    @extend_schema_field(serializers.BooleanField)
    def get_discord_configured(self, obj):
        return bool(obj.discord_webhook)

    @extend_schema_field(serializers.BooleanField)
    def get_telegram_configured(self, obj):
        return bool(obj.telegram_token and obj.telegram_user_id)

    @extend_schema_field(serializers.BooleanField)
    def get_ntfy_configured(self, obj):
        return bool(obj.ntfy_server_url and obj.ntfy_topic)

    @extend_schema_field(serializers.BooleanField)
    def get_webhook_configured(self, obj):
        return bool(obj.webhook_url)

    @extend_schema_field(serializers.BooleanField)
    def get_webhook_signature_configured(self, obj):
        return bool(obj.webhook_secret)

    @extend_schema_field(serializers.BooleanField)
    def get_adguard_configured(self, obj):
        return bool(obj.adguard_url and (not obj.adguard_username or obj.adguard_password))

    @extend_schema_field(serializers.BooleanField)
    def get_pihole_configured(self, obj):
        return bool(obj.pihole_url and obj.pihole_password)

    @extend_schema_field(serializers.BooleanField)
    def get_speedtest_tracker_configured(self, obj):
        return bool(obj.speedtest_tracker_url and obj.speedtest_tracker_api_token)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("homebox_enabled", getattr(self.instance, "homebox_enabled", False)):
            if not attrs.get("homebox_url", getattr(self.instance, "homebox_url", "")):
                raise serializers.ValidationError({"homebox_url": "Enter the HomeBox URL."})
            if not (attrs.get("homebox_api_token") or getattr(self.instance, "homebox_api_token", "")):
                raise serializers.ValidationError({"homebox_api_token": "Enter a HomeBox API key."})
        if (self.instance and self.instance.homebox_api_token and "homebox_url" in attrs
                and attrs["homebox_url"] != self.instance.homebox_url
                and not attrs.get("homebox_api_token")):
            raise serializers.ValidationError({"homebox_api_token": "Enter an API key when changing the HomeBox URL."})
        if "scan_ranges" in attrs:
            attrs["ip_range"] = attrs["scan_ranges"][0]
        elif "ip_range" in attrs:
            attrs["scan_ranges"] = [attrs["ip_range"]]
        scan_ranges = attrs.get(
            "scan_ranges",
            self.instance.effective_scan_ranges if self.instance else [],
        )
        existing_labels = (
            self.instance.effective_scan_range_labels if self.instance else {}
        )
        submitted_labels = attrs.get("scan_range_labels")
        if submitted_labels is not None and not isinstance(submitted_labels, dict):
            raise serializers.ValidationError(
                {"scan_range_labels": "Network names must be provided as an object."}
            )
        normalized_submitted_labels = {}
        if submitted_labels is not None:
            from ..scan import validate_ip_range

            for network_range, label in submitted_labels.items():
                try:
                    normalized_range = validate_ip_range(str(network_range).strip())
                except ValueError as exc:
                    raise serializers.ValidationError(
                        {"scan_range_labels": str(exc)}
                    ) from exc
                if normalized_range not in scan_ranges:
                    raise serializers.ValidationError(
                        {
                            "scan_range_labels": (
                                "Network names may only reference configured ranges."
                            )
                        }
                    )
                normalized_submitted_labels[normalized_range] = label

        labels = {}
        seen_labels = set()
        label_source = (
            normalized_submitted_labels
            if submitted_labels is not None
            else existing_labels
        )
        for index, network_range in enumerate(scan_ranges):
            label = str(label_source.get(network_range) or "").strip()
            if submitted_labels is not None and not label:
                raise serializers.ValidationError(
                    {"scan_range_labels": "Enter a name for every network range."}
                )
            if not label:
                label = default_scan_range_label(index)
            if len(label) > 64:
                raise serializers.ValidationError(
                    {"scan_range_labels": "Network names must be 64 characters or less."}
                )
            normalized_label = label.casefold()
            if normalized_label in seen_labels:
                raise serializers.ValidationError(
                    {"scan_range_labels": "Network names must be unique."}
                )
            seen_labels.add(normalized_label)
            labels[network_range] = label
        attrs["scan_range_labels"] = labels
        webhook_enabled = attrs.get(
            "webhook_enabled",
            self.instance.webhook_enabled if self.instance else False,
        )
        webhook_url = attrs.get(
            "webhook_url",
            self.instance.webhook_url if self.instance else "",
        )
        if webhook_enabled and not webhook_url:
            raise serializers.ValidationError(
                {"webhook_url": "Configure the webhook URL before enabling delivery."}
            )

        ntfy_enabled = attrs.get(
            "ntfy_enabled",
            self.instance.ntfy_enabled if self.instance else False,
        )
        ntfy_server_url = attrs.get(
            "ntfy_server_url",
            self.instance.ntfy_server_url if self.instance else "",
        )
        ntfy_topic = attrs.get(
            "ntfy_topic",
            self.instance.ntfy_topic if self.instance else "",
        )
        if ntfy_enabled and (not ntfy_server_url or not ntfy_topic):
            raise serializers.ValidationError(
                {
                    "ntfy": (
                        "Configure the ntfy server URL and topic before enabling "
                        "delivery."
                    )
                }
            )

        enabled = attrs.get(
            "adguard_enabled",
            self.instance.adguard_enabled if self.instance else False,
        )
        url = attrs.get("adguard_url", self.instance.adguard_url if self.instance else "")
        username = attrs.get(
            "adguard_username",
            self.instance.adguard_username if self.instance else "",
        ).strip()
        password = attrs.get(
            "adguard_password",
            self.instance.adguard_password if self.instance else "",
        )
        if enabled and not url:
            raise serializers.ValidationError(
                {"adguard_url": "Configure the AdGuard Home URL before enabling sync."}
            )
        if enabled and username and not password:
            raise serializers.ValidationError(
                {"adguard_password": "Enter the AdGuard Home password."}
            )

        pihole_enabled = attrs.get(
            "pihole_enabled",
            self.instance.pihole_enabled if self.instance else False,
        )
        pihole_url = attrs.get(
            "pihole_url",
            self.instance.pihole_url if self.instance else "",
        )
        pihole_password = attrs.get("pihole_password") or (
            self.instance.pihole_password if self.instance else ""
        )
        if pihole_enabled and not pihole_url:
            raise serializers.ValidationError(
                {"pihole_url": "Configure the Pi-hole URL before enabling sync."}
            )
        if pihole_enabled and not pihole_password:
            raise serializers.ValidationError(
                {"pihole_password": "Enter a Pi-hole application password."}
            )
        if enabled and pihole_enabled:
            raise serializers.ValidationError(
                {
                    "pihole_enabled": (
                        "Disable AdGuard Home before enabling Pi-hole. Only one DNS "
                        "activity provider can be active at a time."
                    )
                }
            )

        speedtest_enabled = attrs.get(
            "speedtest_tracker_enabled",
            self.instance.speedtest_tracker_enabled if self.instance else False,
        )
        speedtest_url = attrs.get(
            "speedtest_tracker_url",
            self.instance.speedtest_tracker_url if self.instance else "",
        )
        speedtest_token = attrs.get("speedtest_tracker_api_token") or (
            self.instance.speedtest_tracker_api_token if self.instance else ""
        )
        if speedtest_enabled and not speedtest_url:
            raise serializers.ValidationError(
                {"speedtest_tracker_url": "Configure the Speedtest Tracker URL before enabling it."}
            )
        if speedtest_enabled and not speedtest_token:
            raise serializers.ValidationError(
                {"speedtest_tracker_api_token": "Enter a Speedtest Tracker API token."}
            )
        return attrs

    def update(self, instance, validated_data):
        reset_speedtest_baseline = any(
            (
                field in validated_data
                and validated_data[field] != getattr(instance, field)
            )
            for field in (
                "speedtest_tracker_enabled",
                "speedtest_tracker_url",
                "notify_speedtest_changes",
            )
        ) or bool(validated_data.get("speedtest_tracker_api_token"))
        clear_webhook_secret = validated_data.pop("clear_webhook_secret", False)
        if clear_webhook_secret:
            validated_data["webhook_secret"] = ""
        elif not validated_data.get("webhook_secret"):
            validated_data.pop("webhook_secret", None)
        if not validated_data.get("discord_webhook"):
            validated_data.pop("discord_webhook", None)
        if not validated_data.get("adguard_username", instance.adguard_username):
            validated_data.setdefault("adguard_password", "")
        if not validated_data.get("pihole_password"):
            validated_data.pop("pihole_password", None)
        if not validated_data.get("telegram_token"):
            validated_data.pop("telegram_token", None)
        if not validated_data.get("speedtest_tracker_api_token"):
            validated_data.pop("speedtest_tracker_api_token", None)
        if not validated_data.get("homebox_api_token"):
            validated_data.pop("homebox_api_token", None)
        instance = super().update(instance, validated_data)
        if reset_speedtest_baseline:
            instance.speedtest_last_result_id = ""
            instance.speedtest_last_healthy = None
            instance.save(
                update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
            )
        return instance

    def validate_home_map_layout(self, value):
        validate_home_map_layout_value(value)
        return value

    def validate_ip_range(self, value):
        from ..scan import validate_ip_range

        try:
            return validate_ip_range(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_scan_ranges(self, value):
        from ..scan import validate_ip_ranges

        try:
            return validate_ip_ranges(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["scan_ranges"] = instance.effective_scan_ranges
        data["scan_range_labels"] = instance.effective_scan_range_labels
        return data

    def validate_scan_interval(self, value):
        if value < 1:
            raise serializers.ValidationError("Scan interval must be at least 1 minute.")
        if value > 1440:
            raise serializers.ValidationError("Scan interval must be 1440 minutes or less.")
        return value

    def validate_time_zone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError("Enter a valid IANA timezone.") from exc
        return value

    def validate_version_check_interval(self, value):
        if value < 60:
            raise serializers.ValidationError("Version check interval must be at least 1 minute.")
        if value > 604800:
            raise serializers.ValidationError("Version check interval must be 7 days or less.")
        return value

    def validate_activity_cleanup_retention_days(self, value):
        if value < 1:
            raise serializers.ValidationError("Activity cleanup retention must be at least 1 day.")
        if value > 3650:
            raise serializers.ValidationError("Activity cleanup retention must be 3650 days or less.")
        return value

    def validate_adguard_sync_interval(self, value):
        if value < 1:
            raise serializers.ValidationError("AdGuard sync interval must be at least 1 minute.")
        if value > 1440:
            raise serializers.ValidationError("AdGuard sync interval must be 1440 minutes or less.")
        return value

    def validate_adguard_retention_days(self, value):
        if value < 1:
            raise serializers.ValidationError("AdGuard retention must be at least 1 day.")
        if value > 3650:
            raise serializers.ValidationError("AdGuard retention must be 3650 days or less.")
        return value

    def validate_pihole_sync_interval(self, value):
        if value < 1:
            raise serializers.ValidationError("Pi-hole sync interval must be at least 1 minute.")
        if value > 1440:
            raise serializers.ValidationError("Pi-hole sync interval must be 1440 minutes or less.")
        return value

    def validate_pihole_retention_days(self, value):
        if value < 1:
            raise serializers.ValidationError("Pi-hole retention must be at least 1 day.")
        if value > 3650:
            raise serializers.ValidationError("Pi-hole retention must be 3650 days or less.")
        return value

    def validate_notification_quiet_hours_start(self, value):
        return self.validate_quiet_hour(value)

    def validate_notification_quiet_hours_end(self, value):
        return self.validate_quiet_hour(value)

    def validate_notification_quiet_hours_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Select days as a list.")
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Each day can only be selected once.")
        if any(day not in QUIET_HOURS_DAY_KEYS for day in value):
            raise serializers.ValidationError("Select valid weekdays.")
        return [day for day in QUIET_HOURS_DAY_KEYS if day in value]

    def validate_quiet_hour(self, value):
        import datetime

        if len(value) != 5:
            raise serializers.ValidationError("Enter time in HH:MM format.")
        try:
            datetime.time.fromisoformat(value)
        except ValueError as exc:
            raise serializers.ValidationError("Enter time in HH:MM format.") from exc
        return value

