from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError

from ..maintenance import cleanup_activity
from ..user_messages import success_response


@extend_schema(
    request=inline_serializer(
        name="MaintenanceCleanupRequest",
        fields={
            "target": serializers.ChoiceField(
                choices=["events", "scan_runs", "notifications", "dns_activity"]
            ),
            "older_than_days": serializers.IntegerField(
                min_value=1,
                max_value=3650,
                required=False,
            ),
            "clean_all": serializers.BooleanField(required=False),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def maintenance_cleanup(request):
    target = str(request.data.get("target") or "").strip()
    if target not in {"events", "scan_runs", "notifications", "dns_activity"}:
        raise ValidationError(
            {"target": "Must be one of: events, scan_runs, notifications, dns_activity."}
        )

    clean_all = request.data.get("clean_all") is True
    older_than_days = request.data.get("older_than_days", 90)

    if not clean_all:
        try:
            older_than_days = int(older_than_days)
        except (TypeError, ValueError):
            raise ValidationError({"older_than_days": "Must be a number of days."})

        if older_than_days < 1 or older_than_days > 3650:
            raise ValidationError(
                {"older_than_days": "Must be between 1 and 3650 days."}
            )

    result = cleanup_activity(target, older_than_days, clean_all=clean_all)
    deleted = result.get("deleted", {})
    labels = {
        "events": "Events",
        "scan_runs": "Scan history",
        "notifications": "Notifications",
        "dns_activity": "DNS activity",
    }
    if target == "dns_activity":
        message = (
            f"Deleted {deleted.get('dns_activity', 0)} DNS records and "
            f"{deleted.get('dns_unmatched_clients', 0)} unmatched client records."
        )
    else:
        message = (
            f"Deleted {deleted.get('events', 0)} events, "
            f"{deleted.get('scan_runs', 0)} scan runs, and "
            f"{deleted.get('notifications', 0)} notifications."
        )
    return success_response(
        result,
        f"{labels[target]} cleaned",
        message,
    )
