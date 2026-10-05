
from rest_framework import serializers

from ..models import (
    NetworkEvent,
)


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


