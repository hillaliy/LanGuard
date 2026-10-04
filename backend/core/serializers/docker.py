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

class DockerContainerSerializer(serializers.ModelSerializer):
    linked_device_name = serializers.CharField(
        source="linked_device.name",
        read_only=True,
        allow_null=True,
    )
    linked_device_ip = serializers.CharField(
        source="linked_device.ip",
        read_only=True,
        allow_null=True,
    )
    published_ports = serializers.SerializerMethodField()

    class Meta:
        model = DockerContainer
        fields = (
            "id",
            "container_id",
            "name",
            "image",
            "image_id",
            "state",
            "health",
            "status",
            "network_mode",
            "addresses",
            "published_ports",
            "started_at",
            "restart_count",
            "active",
            "first_seen",
            "last_seen",
            "linked_device",
            "linked_device_name",
            "linked_device_ip",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_published_ports(self, obj):
        observed = self.context.get("observed_ports", set())
        return [
            {
                **item,
                "observed_by_languard": (
                    item.get("host_port"), item.get("protocol", "tcp")
                ) in observed,
            }
            for item in obj.published_ports
            if isinstance(item, dict)
        ]


class DockerHostSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_ip = serializers.CharField(source="device.ip", read_only=True)
    container_count = serializers.SerializerMethodField()

    class Meta:
        model = DockerHost
        fields = (
            "id",
            "device",
            "device_name",
            "device_ip",
            "name",
            "enabled",
            "sync_interval",
            "sync_requested",
            "docker_name",
            "docker_version",
            "operating_system",
            "architecture",
            "container_count",
            "last_sync_at",
            "last_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "docker_name",
            "docker_version",
            "operating_system",
            "architecture",
            "sync_requested",
            "last_sync_at",
            "last_error",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.IntegerField)
    def get_container_count(self, obj):
        return obj.containers.filter(active=True).count()

    def validate_sync_interval(self, value):
        if not 1 <= value <= 1440:
            raise serializers.ValidationError("Choose an interval from 1 to 1440 minutes.")
        return value

    def update(self, instance, validated_data):
        host = super().update(instance, validated_data)
        host.sync_requested = True
        host.save(update_fields=["sync_requested", "updated_at"])
        return host


class DockerHostSummarySerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_ip = serializers.CharField(source="device.ip", read_only=True)
    container_count = serializers.SerializerMethodField()

    class Meta:
        model = DockerHost
        fields = (
            "id",
            "device",
            "device_name",
            "device_ip",
            "name",
            "docker_name",
            "docker_version",
            "operating_system",
            "architecture",
            "container_count",
            "last_sync_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField)
    def get_container_count(self, obj):
        return obj.containers.filter(active=True).count()


