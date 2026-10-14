from rest_framework import serializers

HOME_MAP_ROOM_ICON_IDS = {
    "home",
    "living-room",
    "bedroom",
    "kitchen",
    "dining-room",
    "office",
    "bathroom",
    "entrance",
    "garage",
    "basement",
    "garden",
    "outside",
    "laundry",
    "storage",
    "server-room",
}


def validate_home_map_layout_value(value):
    if value in (None, ""):
        return
    if not isinstance(value, dict):
        raise serializers.ValidationError("Home map layout must be an object.")

    order = value.get("order", [])
    parents = value.get("parents", {})
    icons = value.get("icons", {})
    placements = value.get("placements", {})
    sizes = value.get("sizes", {})
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise serializers.ValidationError("Home map layout order must be a list of strings.")
    if not isinstance(parents, dict) or not all(
        isinstance(key, str) and isinstance(parent, str)
        for key, parent in parents.items()
    ):
        raise serializers.ValidationError("Home map layout parents must be an object of strings.")
    if not isinstance(icons, dict) or not all(
        isinstance(room, str)
        and bool(room.strip())
        and isinstance(icon, str)
        and icon in HOME_MAP_ROOM_ICON_IDS
        for room, icon in icons.items()
    ):
        raise serializers.ValidationError(
            "Home map layout icons must map room names to supported icon identifiers."
        )
    if not isinstance(placements, dict) or not all(
        isinstance(room, str)
        and bool(room.strip())
        and isinstance(slot, int)
        and not isinstance(slot, bool)
        and 0 <= slot <= 99
        for room, slot in placements.items()
    ):
        raise serializers.ValidationError(
            "Home map layout placements must map room names to slots from 0 to 99."
        )
    if not isinstance(sizes, dict) or not all(
        isinstance(room, str)
        and bool(room.strip())
        and isinstance(span, int)
        and not isinstance(span, bool)
        and 2 <= span <= 12
        for room, span in sizes.items()
    ):
        raise serializers.ValidationError(
            "Home map layout sizes must map room names to supported column spans."
        )


class HomeMapLayoutSerializer(serializers.Serializer):
    layout = serializers.JSONField(default=dict)

    def validate_layout(self, value):
        validate_home_map_layout_value(value)
        return value or {}
