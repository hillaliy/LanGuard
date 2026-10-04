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


