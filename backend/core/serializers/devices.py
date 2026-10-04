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

class DevicePortSerializer(serializers.ModelSerializer):
    firstseen = UTCDateTimeField(read_only=True)
    lastseen = UTCDateTimeField(read_only=True)
    guidance = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_guidance(self, obj):
        device = self.context.get("device") or obj.device
        return port_guidance(device, obj)

    class Meta:
        model = DevicePort
        fields = "__all__"
        read_only_fields = ("device", "firstseen", "lastseen")


PORT_DENSE_ROLES = {"camera", "intercom", "nas", "server"}

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

    if not device.known:
        score += 3
        reasons.append("New unknown device")

    prefetched_ports = getattr(device, "_prefetched_objects_cache", {}).get("ports")
    if prefetched_ports is None:
        open_ports = list(device.ports.filter(open=True).order_by("port", "protocol"))
    else:
        open_ports = sorted(
            (
                device_port
                for device_port in prefetched_ports
                if device_port.open
            ),
            key=lambda item: (item.port, item.protocol),
        )
    port_findings = [
        (device_port, port_attention(device, device_port))
        for device_port in open_ports
    ]
    port_findings = [item for item in port_findings if item[1] is not None]
    if port_findings:
        score += 3 if any(finding["high_risk"] for _port, finding in port_findings) else 2
        findings = "; ".join(
            (
                f"{device_port.protocol}/{device_port.port} ({finding['label']}): "
                f"{finding['next_step']}"
            )
            for device_port, finding in port_findings
        )
        reasons.append(f"Risky open ports: {findings}")

    if len(open_ports) >= 4 and not (device.known and role in PORT_DENSE_ROLES):
        score += 2
        reasons.append("Many open ports")

    if not device.known and not device.vendor:
        score += 1
        reasons.append("No vendor detected")

    if not device.known and (
        device.status in {Device.Status.RECENTLY_SEEN, Device.Status.SLEEPING}
        or device.missed_scans
    ):
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


ALWAYS_EXPECTED_OFFLINE_DAYS = 7
OCCASIONAL_PRESENCE_OFFLINE_DAYS = 21
OCCASIONAL_PRESENCE_ROLES = frozenset({"laptop", "phone", "tablet", "watch"})
OCCASIONAL_PRESENCE_ICONS = frozenset({"laptop", "phone", "smart-watch", "tablet"})
IDENTITY_CONFLICT_ATTENTION_AFTER = timedelta(days=7)


def device_offline_attention_days(device):
    if device.archived or device.is_visitor:
        return None

    expectation = device.presence_expectation
    if expectation == Device.PresenceExpectation.NEVER:
        return None
    if expectation == Device.PresenceExpectation.AUTOMATIC:
        role = (device.role or "").strip().lower()
        icon = (device.icon or "").strip().lower()
        if role in OCCASIONAL_PRESENCE_ROLES or icon in OCCASIONAL_PRESENCE_ICONS:
            return OCCASIONAL_PRESENCE_OFFLINE_DAYS
        return ALWAYS_EXPECTED_OFFLINE_DAYS

    default_days = (
        OCCASIONAL_PRESENCE_OFFLINE_DAYS
        if expectation == Device.PresenceExpectation.OCCASIONAL
        else ALWAYS_EXPECTED_OFFLINE_DAYS
    )
    return device.offline_attention_after_days or default_days


def device_is_offline_beyond_expectation(device, now=None):
    attention_days = device_offline_attention_days(device)
    return bool(
        attention_days is not None
        and device.status == Device.Status.OFFLINE
        and device.lastseen < (now or timezone.now()) - timedelta(days=attention_days)
    )


def device_attention_reasons(device, risk_data=None):
    current_risk = risk_data or device_risk(device)
    reasons = []
    if not device.known or current_risk["level"] in {"medium", "high"}:
        reasons.extend(current_risk["reasons"])
    if device_is_offline_beyond_expectation(device):
        reasons.append(
            f"Offline for over {device_offline_attention_days(device)} days"
        )
    if (
        device.identity_conflict_reason
        and device.identity_conflict_detected_at
        and device.identity_conflict_detected_at
        >= timezone.now() - IDENTITY_CONFLICT_ATTENTION_AFTER
    ):
        reasons.append(device.identity_conflict_reason)
    return reasons


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
            "offline_over_week": device_is_offline_beyond_expectation(device),
            "identity_conflict_reason": device.identity_conflict_reason,
            "identity_conflict_detected_at": (
                device.identity_conflict_detected_at.isoformat()
                if device.identity_conflict_detected_at
                else ""
            ),
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
    requires_attention = bool(device_attention_reasons(device, current_risk))
    return requires_attention and not device_attention_acknowledged(device, current_risk)


class DeviceSerializer(serializers.ModelSerializer):
    homebox_link = serializers.SerializerMethodField()
    homebox_available = serializers.SerializerMethodField()
    effective_external_url = serializers.CharField(read_only=True)
    offline_attention_effective_days = serializers.SerializerMethodField()

    def homebox_config(self):
        if "homebox_config" not in self.context:
            self.context["homebox_config"] = AppSettings.load()
        return self.context["homebox_config"]

    @extend_schema_field(serializers.BooleanField)
    def get_homebox_available(self, obj):
        config = self.homebox_config()
        return bool(config.homebox_enabled and config.homebox_url and config.homebox_api_token)

    @extend_schema_field(serializers.CharField)
    def get_homebox_link(self, obj):
        if obj.homebox_item_id and self.get_homebox_available(obj):
            return f"{self.homebox_config().homebox_url.rstrip('/')}/item/{obj.homebox_item_id}"
        return ""

    def validate_homebox_item_id(self, value):
        if not value or (self.instance and value == self.instance.homebox_item_id):
            return value
        from ..homebox import HomeBoxClient, HomeBoxError
        config = self.homebox_config()
        if not config.homebox_enabled:
            raise serializers.ValidationError("Enable HomeBox before linking an item.")
        try:
            HomeBoxClient(config.homebox_url, config.homebox_api_token).item(value)
        except HomeBoxError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    hostname_source = serializers.CharField(read_only=True)
    vendor_source = serializers.CharField(read_only=True)
    attention_acknowledged_signature = serializers.HiddenField(
        default=serializers.CreateOnlyDefault("")
    )
    firstseen = UTCDateTimeField(read_only=True)
    lastseen = UTCDateTimeField(read_only=True)
    last_status_check = UTCDateTimeField(read_only=True)
    last_port_scan = UTCDateTimeField(read_only=True)
    identity_conflict_detected_at = UTCDateTimeField(read_only=True)
    open_ports = serializers.SerializerMethodField()
    risk_level = serializers.SerializerMethodField()
    risk_score = serializers.SerializerMethodField()
    risk_reasons = serializers.SerializerMethodField()
    attention_reasons = serializers.SerializerMethodField()
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
    presence_expectation_display = serializers.CharField(
        source="get_presence_expectation_display",
        read_only=True,
    )

    class Meta:
        model = Device
        fields = "__all__"
        read_only_fields = (
            "hostname",
            "vendor",
            "hostname_source",
            "vendor_source",
            "identity_conflict_reason",
            "identity_conflict_detected_at",
        )

    def get_device_identity(self, obj):
        if not hasattr(obj, "_identity_data"):
            obj._identity_data = device_identity(obj)
        return obj._identity_data

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_offline_attention_effective_days(self, obj):
        return device_offline_attention_days(obj)

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

        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise serializers.ValidationError("Enter a valid HTTP or HTTPS URL.")
        return value

    @extend_schema_field(DevicePortSerializer(many=True))
    def get_open_ports(self, obj):
        return DevicePortSerializer(
            obj.ports.filter(open=True),
            many=True,
            context={**self.context, "device": obj},
        ).data

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

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_attention_reasons(self, obj):
        return device_attention_reasons(obj, self.get_device_risk(obj))

    @extend_schema_field(serializers.BooleanField)
    def get_attention_acknowledged(self, obj):
        return device_attention_acknowledged(obj, self.get_device_risk(obj))

    @extend_schema_field(serializers.BooleanField)
    def get_needs_attention(self, obj):
        return device_needs_attention(obj, self.get_device_risk(obj))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        requested_known = attrs.get("known")
        requested_visitor = attrs.get("is_visitor")
        if requested_known is False and requested_visitor is True:
            raise serializers.ValidationError(
                {"is_visitor": "Visitor devices must be known devices."}
            )
        if requested_visitor is True:
            attrs["known"] = True
        elif requested_known is False:
            attrs["is_visitor"] = False

        known = attrs.get("known", self.instance.known if self.instance else False)
        if attrs.get("acknowledge_attention") and not known:
            raise serializers.ValidationError(
                {"acknowledge_attention": "Only known devices can be acknowledged."}
            )

        presence_expectation = attrs.get(
            "presence_expectation",
            self.instance.presence_expectation
            if self.instance
            else Device.PresenceExpectation.AUTOMATIC,
        )
        offline_attention_after_days = attrs.get(
            "offline_attention_after_days",
            self.instance.offline_attention_after_days if self.instance else None,
        )
        if presence_expectation in {
            Device.PresenceExpectation.AUTOMATIC,
            Device.PresenceExpectation.NEVER,
        }:
            attrs["offline_attention_after_days"] = None
        elif (
            offline_attention_after_days is not None
            and not 1 <= offline_attention_after_days <= 3650
        ):
            raise serializers.ValidationError(
                {
                    "offline_attention_after_days": (
                        "Choose a value between 1 and 3650 days."
                    )
                }
            )

        external_url = attrs.get(
            "external_url",
            self.instance.external_url if self.instance else "",
        )
        follow_device_ip = attrs.get(
            "external_url_follow_device_ip",
            self.instance.external_url_follow_device_ip if self.instance else False,
        )
        if not external_url:
            attrs["external_url_follow_device_ip"] = False
        elif follow_device_ip:
            try:
                hostname = urlparse(external_url).hostname
                if ipaddress.ip_address(hostname).version != 4:
                    raise ValueError
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    {
                        "external_url_follow_device_ip": (
                            "Follow device IP requires an External link with an IPv4 hostname."
                        )
                    }
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


class DeviceBulkUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )
    known = serializers.BooleanField(required=False)
    is_visitor = serializers.BooleanField(required=False)
    acknowledge_attention = serializers.BooleanField(required=False)

    def validate_ids(self, value):
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        if not any(
            field in attrs
            for field in ("known", "is_visitor", "acknowledge_attention")
        ):
            raise serializers.ValidationError(
                "Provide known, is_visitor, or acknowledge_attention for the selected devices."
            )
        if "acknowledge_attention" in attrs:
            if attrs["acknowledge_attention"] is not True:
                raise serializers.ValidationError(
                    {"acknowledge_attention": "This bulk action must be true."}
                )
            if "known" in attrs or "is_visitor" in attrs:
                raise serializers.ValidationError(
                    {
                        "acknowledge_attention": (
                            "Review attention separately from device classification."
                        )
                    }
                )
        if attrs.get("known") is False and attrs.get("is_visitor") is True:
            raise serializers.ValidationError(
                {"is_visitor": "Visitor devices must be known devices."}
            )
        return attrs


