
from rest_framework import serializers

from ..models import (
    AdGuardUnmatchedClient,
    DeviceDNSActivity,
)


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


