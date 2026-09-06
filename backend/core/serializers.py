import hashlib
import json

from django.conf import settings
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .access_control import ACCESS_FIELDS, update_user_capabilities, user_capabilities
from .datetime_utils import utc_isoformat
from .models import (
    AdGuardUnmatchedClient,
    AppSettings,
    Device,
    DeviceDNSActivity,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    QUIET_HOURS_DAY_KEYS,
    ScanRun,
    default_scan_range_label,
)
from .user_messages import stored_error_message


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
    can_edit_devices = serializers.BooleanField(write_only=True, required=False, default=True)
    can_edit_home_map = serializers.BooleanField(write_only=True, required=False, default=True)
    can_run_scans = serializers.BooleanField(write_only=True, required=False, default=True)

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
            "can_edit_devices",
            "can_edit_home_map",
            "can_run_scans",
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
        capability_values = {
            field: validated_data.pop(field)
            for field in ACCESS_FIELDS
            if field in validated_data
        }
        user = User.objects.create_user(password=password, **validated_data)
        update_user_capabilities(user, capability_values)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        validated_data.pop("password_confirm", None)
        capability_values = {
            field: validated_data.pop(field)
            for field in ACCESS_FIELDS
            if field in validated_data
        }

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        update_user_capabilities(instance, capability_values)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(user_capabilities(instance))
        return data


class DevicePortSerializer(serializers.ModelSerializer):
    firstseen = UTCDateTimeField(read_only=True)
    lastseen = UTCDateTimeField(read_only=True)

    class Meta:
        model = DevicePort
        fields = "__all__"
        read_only_fields = ("device", "firstseen", "lastseen")


class DeviceDNSActivitySerializer(serializers.ModelSerializer):
    first_seen = UTCDateTimeField(read_only=True)
    last_seen = UTCDateTimeField(read_only=True)

    class Meta:
        model = DeviceDNSActivity
        fields = (
            "id",
            "domain",
            "query_type",
            "query_count",
            "blocked_count",
            "first_seen",
            "last_seen",
            "last_status",
            "last_reason",
            "last_service_name",
        )
        read_only_fields = fields


class GlobalDNSActivitySerializer(DeviceDNSActivitySerializer):
    device_id = serializers.IntegerField(source="device.id", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_ip = serializers.CharField(source="device.ip", read_only=True)
    device_mac = serializers.CharField(source="device.mac", read_only=True)

    class Meta(DeviceDNSActivitySerializer.Meta):
        fields = DeviceDNSActivitySerializer.Meta.fields + (
            "device_id",
            "device_name",
            "device_ip",
            "device_mac",
        )


class AdGuardUnmatchedClientSerializer(serializers.ModelSerializer):
    first_seen = UTCDateTimeField(read_only=True)
    last_seen = UTCDateTimeField(read_only=True)

    class Meta:
        model = AdGuardUnmatchedClient
        fields = (
            "id",
            "client",
            "query_count",
            "blocked_count",
            "first_seen",
            "last_seen",
            "last_domain",
            "last_status",
            "last_reason",
        )
        read_only_fields = fields


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

HIGH_CONFIDENCE_IDENTITY_SOURCES = {
    Device.IdentitySource.REVERSE_DNS,
    Device.IdentitySource.MDNS,
    Device.IdentitySource.LLMNR,
    Device.IdentitySource.NETBIOS,
    Device.IdentitySource.SNMP,
    Device.IdentitySource.MANUF,
}
MEDIUM_CONFIDENCE_IDENTITY_SOURCES = {
    Device.IdentitySource.SSDP,
    Device.IdentitySource.HTTP,
    Device.IdentitySource.ARP,
    Device.IdentitySource.IMPORTED,
}


def identity_field_confidence(value, source):
    if not (value or "").strip():
        return "none"
    if source in HIGH_CONFIDENCE_IDENTITY_SOURCES:
        return "high"
    if source in MEDIUM_CONFIDENCE_IDENTITY_SOURCES:
        return "medium"
    return "low"


def device_identity(device):
    hostname_confidence = identity_field_confidence(device.hostname, device.hostname_source)
    vendor_confidence = identity_field_confidence(device.vendor, device.vendor_source)
    field_confidences = {hostname_confidence, vendor_confidence}

    if hostname_confidence == "high" and vendor_confidence == "high":
        confidence = "high"
    elif "high" in field_confidences or (
        hostname_confidence == "medium" and vendor_confidence == "medium"
    ):
        confidence = "medium"
    else:
        confidence = "low"

    evidence = []
    if device.hostname:
        evidence.append({
            "field": "hostname",
            "value": device.hostname,
            "source": device.hostname_source,
            "source_display": device.get_hostname_source_display() if device.hostname_source else "Unknown",
            "confidence": hostname_confidence,
        })
    if device.vendor:
        evidence.append({
            "field": "vendor",
            "value": device.vendor,
            "source": device.vendor_source,
            "source_display": device.get_vendor_source_display() if device.vendor_source else "Unknown",
            "confidence": vendor_confidence,
        })

    return {
        "confidence": confidence,
        "hostname_confidence": hostname_confidence,
        "vendor_confidence": vendor_confidence,
        "evidence": evidence,
    }


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
    hostname_source = serializers.CharField(read_only=True)
    vendor_source = serializers.CharField(read_only=True)
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
    identity_confidence = serializers.SerializerMethodField()
    hostname_confidence = serializers.SerializerMethodField()
    vendor_confidence = serializers.SerializerMethodField()
    identity_evidence = serializers.SerializerMethodField()
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
        read_only_fields = ("hostname", "vendor", "hostname_source", "vendor_source")

    def get_device_identity(self, obj):
        if not hasattr(obj, "_identity_data"):
            obj._identity_data = device_identity(obj)
        return obj._identity_data

    @extend_schema_field(serializers.CharField)
    def get_identity_confidence(self, obj):
        return self.get_device_identity(obj)["confidence"]

    @extend_schema_field(serializers.CharField)
    def get_hostname_confidence(self, obj):
        return self.get_device_identity(obj)["hostname_confidence"]

    @extend_schema_field(serializers.CharField)
    def get_vendor_confidence(self, obj):
        return self.get_device_identity(obj)["vendor_confidence"]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_identity_evidence(self, obj):
        return self.get_device_identity(obj)["evidence"]

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
    error = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField)
    def get_error(self, obj):
        return stored_error_message("scan", obj.error)

    class Meta:
        model = ScanRun
        fields = "__all__"


class DeviceBulkUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )
    known = serializers.BooleanField()

    def validate_ids(self, value):
        return list(dict.fromkeys(value))


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
    telegram_user_id = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )

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
        elif channel == NotificationDelivery.Channel.WEBHOOK:
            if not attrs.get("webhook_url", "").strip():
                raise serializers.ValidationError(
                    {"webhook_url": "Enter a webhook URL."}
                )
        return attrs


class AdGuardConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    username = serializers.CharField(required=False, allow_blank=True, max_length=255)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        username = attrs.get("username", "").strip()
        password = attrs.get("password", "")
        if username and not password:
            saved = AppSettings.load()
            if not saved.adguard_password:
                raise serializers.ValidationError(
                    {"password": "Enter the AdGuard Home password."}
                )
        return attrs


class SpeedtestTrackerConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    api_token = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=512,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        saved = AppSettings.load()
        if not attrs.get("api_token") and not saved.speedtest_tracker_api_token:
            raise serializers.ValidationError(
                {"api_token": "Enter a Speedtest Tracker API token."}
            )
        return attrs


class AppSettingsSerializer(serializers.ModelSerializer):
    updated_at = UTCDateTimeField(read_only=True)
    adguard_last_sync_at = UTCDateTimeField(read_only=True)
    scan_max_hosts = serializers.SerializerMethodField()
    discord_configured = serializers.SerializerMethodField()
    telegram_configured = serializers.SerializerMethodField()
    webhook_configured = serializers.SerializerMethodField()
    webhook_signature_configured = serializers.SerializerMethodField()
    adguard_configured = serializers.SerializerMethodField()
    speedtest_tracker_configured = serializers.SerializerMethodField()
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
    telegram_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
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

    @extend_schema_field(serializers.CharField)
    def get_adguard_last_error(self, obj):
        return stored_error_message("adguard", obj.adguard_last_error)

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
            "telegram_token",
            "telegram_user_id",
            "telegram_configured",
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
            "speedtest_tracker_enabled",
            "speedtest_tracker_url",
            "speedtest_tracker_api_token",
            "speedtest_tracker_configured",
            "home_map_layout",
            "updated_at",
        )
        extra_kwargs = {
            "telegram_user_id": {"required": False, "allow_blank": True},
            "webhook_url": {"required": False, "allow_blank": True},
            "adguard_url": {"required": False, "allow_blank": True},
            "adguard_username": {"required": False, "allow_blank": True},
            "adguard_last_sync_at": {"read_only": True},
            "adguard_last_error": {"read_only": True},
            "speedtest_tracker_url": {"required": False, "allow_blank": True},
            "updated_at": {"read_only": True},
        }

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
    def get_webhook_configured(self, obj):
        return bool(obj.webhook_url)

    @extend_schema_field(serializers.BooleanField)
    def get_webhook_signature_configured(self, obj):
        return bool(obj.webhook_secret)

    @extend_schema_field(serializers.BooleanField)
    def get_adguard_configured(self, obj):
        return bool(obj.adguard_url and (not obj.adguard_username or obj.adguard_password))

    @extend_schema_field(serializers.BooleanField)
    def get_speedtest_tracker_configured(self, obj):
        return bool(obj.speedtest_tracker_url and obj.speedtest_tracker_api_token)

    def validate(self, attrs):
        attrs = super().validate(attrs)
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
            from .scan import validate_ip_range

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
        clear_webhook_secret = validated_data.pop("clear_webhook_secret", False)
        if clear_webhook_secret:
            validated_data["webhook_secret"] = ""
        elif not validated_data.get("webhook_secret"):
            validated_data.pop("webhook_secret", None)
        if not validated_data.get("discord_webhook"):
            validated_data.pop("discord_webhook", None)
        if not validated_data.get("adguard_username", instance.adguard_username):
            validated_data.setdefault("adguard_password", "")
        if not validated_data.get("telegram_token"):
            validated_data.pop("telegram_token", None)
        if not validated_data.get("speedtest_tracker_api_token"):
            validated_data.pop("speedtest_tracker_api_token", None)
        return super().update(instance, validated_data)

    def validate_home_map_layout(self, value):
        validate_home_map_layout_value(value)
        return value

    def validate_ip_range(self, value):
        from .scan import validate_ip_range

        try:
            return validate_ip_range(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_scan_ranges(self, value):
        from .scan import validate_ip_ranges

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
