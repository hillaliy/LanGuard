
from rest_framework import serializers




def validate_home_map_layout_value(value):
    if value in (None, ""):
        return
    if not isinstance(value, dict):
        raise serializers.ValidationError("Home map layout must be an object.")

    order = value.get("order", [])
    parents = value.get("parents", {})
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise serializers.ValidationError("Home map layout order must be a list of strings.")
    if not isinstance(parents, dict) or not all(
        isinstance(key, str) and isinstance(parent, str)
        for key, parent in parents.items()
    ):
        raise serializers.ValidationError("Home map layout parents must be an object of strings.")


class HomeMapLayoutSerializer(serializers.Serializer):
    layout = serializers.JSONField(default=dict)

    def validate_layout(self, value):
        validate_home_map_layout_value(value)
        return value or {}
