from rest_framework import serializers

from ..datetime_utils import utc_isoformat


class UTCDateTimeField(serializers.DateTimeField):
    def to_representation(self, value):
        return utc_isoformat(value)


