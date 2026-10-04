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


class DetailedPortScanSerializer(serializers.ModelSerializer):
    created_at = UTCDateTimeField(read_only=True)
    started_at = UTCDateTimeField(read_only=True)
    finished_at = UTCDateTimeField(read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_ip = serializers.CharField(source="device.ip", read_only=True)
    requested_by = serializers.CharField(
        source="requested_by.username",
        read_only=True,
        allow_null=True,
    )
    progress_percent = serializers.SerializerMethodField()
    open_ports = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField(min_value=0, max_value=100))
    def get_progress_percent(self, obj):
        if not obj.total_ports:
            return 0
        return min(100, round((obj.scanned_ports / obj.total_ports) * 100))

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_open_ports(self, obj):
        return [
            {**port, "guidance": port_guidance(obj.device, port)}
            for port in (obj.open_ports or [])
        ]

    class Meta:
        model = DetailedPortScan
        fields = (
            "id",
            "device",
            "device_name",
            "device_ip",
            "requested_by",
            "open_ports",
            "status",
            "total_ports",
            "scanned_ports",
            "progress_percent",
            "cancel_requested",
            "created_at",
            "started_at",
            "finished_at",
            "error",
        )


