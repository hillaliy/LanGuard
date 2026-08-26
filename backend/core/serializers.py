import hashlib
import json

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from django.contrib.auth.models import User
from .datetime_utils import utc_isoformat
from .models import (
    AppSettings,
    Device,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)


def capitalize_name(value):
    def capitalize_part(part):
        return part[:1].upper() + part[1:].lower() if part else part

    return " ".join(
        "-".join(capitalize_part(part) for part in word.split("-"))
        for word in (value or "").strip().split()
    )


class UTCDateTimeField(serializers.DateTimeField):
    def to_representation(self, value):
        return utc_isoformat(value)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "password", "password_confirm")

    def create(self, validated_data):
        password = validated_data.pop("password")
        password_confirm = validated_data.pop("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError("Passwords do not match.")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user


class UserManagementSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "date_joined", "last_login")

    def validate(self, attrs):
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")
        if "first_name" in attrs:
            attrs["first_name"] = capitalize_name(attrs["first_name"])
        if "last_name" in attrs:
            attrs["last_name"] = capitalize_name(attrs["last_name"])

        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required."})
        if password and password != password_confirm:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm", None)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        validated_data.pop("password_confirm", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class DevicePortSerializer(serializers.ModelSerializer):
    firstseen = UTCDateTimeField(read_only=True)
    lastseen = UTCDateTimeField(read_only=True)

    class Meta:
        model = DevicePort
        fields = "__all__"
        read_only_fields = ("device", "firstseen", "lastseen")


RISKY_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    445: "SMB",
    3389: "Remote Desktop",
    5900: "VNC",
    8080: "Admin web",
}
HIGH_RISK_PORTS = {23, 445, 3389, 5900}
ROLE_EXPECTED_PORTS = {
    "camera": {80, 443, 554, 8000, 8080, 8443, 8554},
    "intercom": {80, 443, 554, 8000, 8080, 8443, 8554},
    "server": {22, 80, 443, 445, 3000, 5000, 8080, 8443},
}
PORT_DENSE_ROLES = {"camera", "intercom", "server"}


def device_risk(device):
    score = 0
    reasons = []
    role = (device.role or "").strip().lower()
    expected_ports = ROLE_EXPECTED_PORTS.get(role, set()) if device.known else set()

    if not device.known:
        score += 3
        reasons.append("New unknown device")

    open_ports = list(
        device.ports.filter(open=True)
        .order_by("port", "protocol")
        .values_list("port", "protocol")
    )
    risky_ports = [
        f"{protocol}/{port} ({RISKY_PORTS[port]})"
        for port, protocol in open_ports
        if port in RISKY_PORTS and port not in expected_ports
    ]
    if risky_ports:
        high_risk_count = sum(
            1 for port, _protocol in open_ports if port in HIGH_RISK_PORTS and port not in expected_ports
        )
        score += 3 if high_risk_count else 2
        reasons.append(f"Risky open ports: {', '.join(risky_ports)}")

    if len(open_ports) >= 4 and not (device.known and role in PORT_DENSE_ROLES):
        score += 2
        reasons.append("Many open ports")

    if not device.vendor:
        score += 1
        reasons.append("No vendor detected")

    if device.status in {Device.Status.RECENTLY_SEEN, Device.Status.SLEEPING} or device.missed_scans:
        score += 1
        reasons.append("Recently missed scans")

    if score >= 5:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "score": score,
        "reasons": reasons,
    }


def device_risk_signature(device, risk_data=None):
    current_risk = risk_data or device_risk(device)
    payload = json.dumps(
        {
            "known": device.known,
            "role": (device.role or "").strip().lower(),
            "open_ports": list(
                device.ports.filter(open=True)
                .order_by("port", "protocol")
                .values_list("port", "protocol")
            ),
            "risk_level": current_risk["level"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def device_attention_acknowledged(device, risk_data=None):
    if not device.known or not device.attention_acknowledged_signature:
        return False
    current_risk = risk_data or device_risk(device)
    return device.attention_acknowledged_signature == device_risk_signature(device, current_risk)


def device_needs_attention(device, risk_data=None):
    current_risk = risk_data or device_risk(device)
    requires_attention = not device.known or current_risk["level"] in {"medium", "high"}
    return requires_attention and not device_attention_acknowledged(device, current_risk)


class DeviceSerializer(serializers.ModelSerializer):
    attention_acknowledged_signature = serializers.HiddenField(
        default=serializers.CreateOnlyDefault("")
    )
    firstseen = UTCDateTimeField(read_only=True)
    lastseen = UTCDateTimeField(read_only=True)
    last_status_check = UTCDateTimeField(read_only=True)
    last_port_scan = UTCDateTimeField(read_only=True)
    open_ports = serializers.SerializerMethodField()
    risk_level = serializers.SerializerMethodField()
    risk_score = serializers.SerializerMethodField()
    risk_reasons = serializers.SerializerMethodField()
    attention_acknowledged = serializers.SerializerMethodField()
    needs_attention = serializers.SerializerMethodField()
    acknowledge_attention = serializers.BooleanField(write_only=True, required=False)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    status_source_display = serializers.CharField(
        source="get_status_source_display",
        read_only=True,
    )

    class Meta:
        model = Device
        fields = "__all__"

    def validate_external_url(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise serializers.ValidationError("Enter a valid HTTP or HTTPS URL.")
        return value

    @extend_schema_field(DevicePortSerializer(many=True))
    def get_open_ports(self, obj):
        return DevicePortSerializer(obj.ports.filter(open=True), many=True).data

    def get_device_risk(self, obj):
        if not hasattr(obj, "_risk_data"):
            obj._risk_data = device_risk(obj)
        return obj._risk_data

    @extend_schema_field(serializers.CharField)
    def get_risk_level(self, obj):
        return self.get_device_risk(obj)["level"]

    @extend_schema_field(serializers.IntegerField)
    def get_risk_score(self, obj):
        return self.get_device_risk(obj)["score"]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_risk_reasons(self, obj):
        return self.get_device_risk(obj)["reasons"]

    @extend_schema_field(serializers.BooleanField)
    def get_attention_acknowledged(self, obj):
        return device_attention_acknowledged(obj, self.get_device_risk(obj))

    @extend_schema_field(serializers.BooleanField)
    def get_needs_attention(self, obj):
        return device_needs_attention(obj, self.get_device_risk(obj))

    def validate(self, attrs):
        known = attrs.get("known", self.instance.known if self.instance else False)
        if attrs.get("acknowledge_attention") and not known:
            raise serializers.ValidationError(
                {"acknowledge_attention": "Only known devices can be acknowledged."}
            )
        return attrs

    def update(self, instance, validated_data):
        acknowledge_attention = validated_data.pop("acknowledge_attention", None)
        instance = super().update(instance, validated_data)
        if not instance.known:
            instance.attention_acknowledged_signature = ""
            instance.save(update_fields=["attention_acknowledged_signature"])
        elif acknowledge_attention is not None:
            instance.attention_acknowledged_signature = (
                device_risk_signature(instance) if acknowledge_attention else ""
            )
            instance.save(update_fields=["attention_acknowledged_signature"])
        return instance


class ScanRunSerializer(serializers.ModelSerializer):
    started_at = UTCDateTimeField(read_only=True)
    finished_at = UTCDateTimeField(read_only=True)

    class Meta:
        model = ScanRun
        fields = "__all__"


class NetworkEventSerializer(serializers.ModelSerializer):
    created_at = UTCDateTimeField(read_only=True)
    event_type_display = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    class Meta:
        model = NetworkEvent
        fields = "__all__"


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

    class Meta:
        model = NotificationDelivery
        fields = "__all__"


class NotificationTestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=(
            NotificationDelivery.Channel.DISCORD,
            NotificationDelivery.Channel.TELEGRAM,
        )
    )
    discord_webhook = serializers.URLField(required=False, allow_blank=True)
    telegram_token = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    telegram_user_id = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )

    def validate(self, attrs):
        channel = attrs["channel"]
        if channel == NotificationDelivery.Channel.DISCORD:
            if not attrs.get("discord_webhook", "").strip():
                raise serializers.ValidationError(
                    {"discord_webhook": "Enter a Discord webhook URL."}
                )
        elif not attrs.get("telegram_token", "").strip() or not attrs.get(
            "telegram_user_id", ""
        ).strip():
            raise serializers.ValidationError(
                {
                    "telegram": (
                        "Enter both a Telegram bot token and user ID."
                    )
                }
            )
        return attrs


class AppSettingsSerializer(serializers.ModelSerializer):
    updated_at = UTCDateTimeField(read_only=True)
    discord_configured = serializers.SerializerMethodField()
    telegram_configured = serializers.SerializerMethodField()

    class Meta:
        model = AppSettings
        fields = (
            "ip_range",
            "scan_interval",
            "time_zone",
            "version_check_interval",
            "notifications_enabled",
            "discord_enabled",
            "discord_webhook",
            "discord_configured",
            "telegram_enabled",
            "telegram_token",
            "telegram_user_id",
            "telegram_configured",
            "notify_new_devices",
            "notify_device_online",
            "notify_device_offline",
            "notify_port_changes",
            "notification_quiet_hours_enabled",
            "notification_quiet_hours_start",
            "notification_quiet_hours_end",
            "activity_cleanup_retention_days",
            "home_map_layout",
            "updated_at",
        )
        extra_kwargs = {
            "discord_webhook": {"required": False, "allow_blank": True},
            "telegram_token": {"required": False, "allow_blank": True},
            "telegram_user_id": {"required": False, "allow_blank": True},
            "updated_at": {"read_only": True},
        }

    @extend_schema_field(serializers.BooleanField)
    def get_discord_configured(self, obj):
        return bool(obj.discord_webhook)

    @extend_schema_field(serializers.BooleanField)
    def get_telegram_configured(self, obj):
        return bool(obj.telegram_token and obj.telegram_user_id)

    def validate_home_map_layout(self, value):
        validate_home_map_layout_value(value)
        return value

    def validate_ip_range(self, value):
        from .scan import validate_ip_range

        try:
            return validate_ip_range(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

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

    def validate_notification_quiet_hours_start(self, value):
        return self.validate_quiet_hour(value)

    def validate_notification_quiet_hours_end(self, value):
        return self.validate_quiet_hour(value)

    def validate_quiet_hour(self, value):
        import datetime

        if len(value) != 5:
            raise serializers.ValidationError("Enter time in HH:MM format.")
        try:
            datetime.time.fromisoformat(value)
        except ValueError as exc:
            raise serializers.ValidationError("Enter time in HH:MM format.") from exc
        return value


def validate_home_map_layout_value(value):
    if value in (None, ""):
        return
    if not isinstance(value, dict):
        raise serializers.ValidationError("Home map layout must be an object.")

    order = value.get("order", [])
    parents = value.get("parents", {})
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise serializers.ValidationError("Home map layout order must be a list of strings.")
    if not isinstance(parents, dict) or not all(
        isinstance(key, str) and isinstance(parent, str)
        for key, parent in parents.items()
    ):
        raise serializers.ValidationError("Home map layout parents must be an object of strings.")


class HomeMapLayoutSerializer(serializers.Serializer):
    layout = serializers.JSONField(default=dict)

    def validate_layout(self, value):
        validate_home_map_layout_value(value)
        return value or {}
