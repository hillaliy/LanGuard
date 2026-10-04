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

class NetworkEventSerializer(serializers.ModelSerializer):
    created_at = UTCDateTimeField(read_only=True)
    event_type_display = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    class Meta:
        model = NetworkEvent
        fields = "__all__"


