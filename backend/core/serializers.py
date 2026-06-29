from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from django.contrib.auth.models import User
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
    class Meta:
        model = DevicePort
        fields = "__all__"
        read_only_fields = ("device", "firstseen", "lastseen")


class DeviceSerializer(serializers.ModelSerializer):
    open_ports = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = "__all__"

    @extend_schema_field(DevicePortSerializer(many=True))
    def get_open_ports(self, obj):
        return DevicePortSerializer(obj.ports.filter(open=True), many=True).data


class ScanRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanRun
        fields = "__all__"


class NetworkEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    class Meta:
        model = NetworkEvent
        fields = "__all__"


class NotificationDeliverySerializer(serializers.ModelSerializer):
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


class AppSettingsSerializer(serializers.ModelSerializer):
    discord_configured = serializers.SerializerMethodField()
    telegram_configured = serializers.SerializerMethodField()

    class Meta:
        model = AppSettings
        fields = (
            "ip_range",
            "scan_interval",
            "time_zone",
            "notifications_enabled",
            "discord_enabled",
            "discord_webhook",
            "discord_configured",
            "telegram_enabled",
            "telegram_token",
            "telegram_user_id",
            "telegram_configured",
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
