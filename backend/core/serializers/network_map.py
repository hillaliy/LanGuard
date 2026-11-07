import math

from rest_framework import serializers

from ..models import Device, NetworkLink
from ..network_map import endpoint_registry, link_signature, logical_id


class NetworkLinkSerializer(serializers.ModelSerializer):
    source = serializers.PrimaryKeyRelatedField(queryset=Device.objects.filter(archived=False, is_visitor=False))
    target = serializers.PrimaryKeyRelatedField(queryset=Device.objects.filter(archived=False, is_visitor=False))

    class Meta:
        model = NetworkLink
        fields = ("id", "source", "target", "source_port", "target_port", "kind", "label", "revision")
        read_only_fields = ("id", "revision")

    def validate(self, attrs):
        for field in ("source_port", "target_port", "label", "kind"):
            attrs.setdefault(field, getattr(self.instance, field, "unknown" if field == "kind" else ""))
        source, target = attrs["source"], attrs["target"]
        _, interfaces = endpoint_registry()
        if source.pk not in interfaces or target.pk not in interfaces:
            raise serializers.ValidationError("Both interfaces must belong to active regular devices.")
        if logical_id(source) == logical_id(target):
            raise serializers.ValidationError("Choose two different logical devices.")
        signature = link_signature(source.pk, target.pk, attrs.get("source_port", ""), attrs.get("target_port", ""))
        duplicates = NetworkLink.objects.filter(signature=signature)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("This interface and port connection already exists.")
        attrs["signature"] = signature
        return attrs


class NetworkLayoutSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    positions = serializers.JSONField()

    def validate_positions(self, value):
        if not isinstance(value, dict) or len(value) > 10000:
            raise serializers.ValidationError("Positions must be an object with at most 10,000 devices.")
        result = {}
        for key, position in value.items():
            if (not isinstance(key, str) or len(key) > 19 or not key.isascii() or not key.isdecimal()
                    or not 0 < int(key) <= 9223372036854775807 or key != str(int(key))
                    or not isinstance(position, dict) or set(position) != {"x", "y"}):
                raise serializers.ValidationError("Each device ID must have an x and y position.")
            if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or abs(v) > 1_000_000
                   for v in position.values()):
                raise serializers.ValidationError("Coordinates must be finite numbers within the supported canvas.")
            result[str(int(key))] = position
        if Device.objects.filter(pk__in=[int(key) for key in result]).count() != len(result):
            raise serializers.ValidationError("Positions must refer to inventoried devices.")
        return result


class NetworkRevisionSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1)


class NetworkMapPreferenceSerializer(serializers.Serializer):
    show_lldp_suggestions = serializers.BooleanField(required=True)


class NetworkBulkLinksSerializer(serializers.Serializer):
    connections = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=200)
