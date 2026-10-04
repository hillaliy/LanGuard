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


class PiHoleConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        saved = AppSettings.load()
        if not attrs.get("password") and not saved.pihole_password:
            raise serializers.ValidationError(
                {"password": "Enter a Pi-hole application password."}
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


