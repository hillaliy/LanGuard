from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import AppSettings
from ..scan import mark_devices_outside_scan_ranges_offline
from ..serializers.settings import AppSettingsSerializer
from ..user_messages import success_response
from ..versioning import fetch_latest_version


@extend_schema(
    responses=inline_serializer(
        name="VersionStatusResponse",
        fields={
            "data": inline_serializer(
                name="VersionStatus",
                fields={
                    "current_version": serializers.CharField(),
                    "latest_version": serializers.CharField(allow_null=True),
                    "check_interval_seconds": serializers.IntegerField(),
                },
            )
        },
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def version_status(request):
    latest_version = fetch_latest_version()
    config = AppSettings.load()
    return Response(
        {
            "data": {
                "current_version": settings.APP_VERSION,
                "latest_version": latest_version,
                "check_interval_seconds": config.version_check_interval,
            }
        }
    )


@extend_schema(
    request=AppSettingsSerializer,
    responses=AppSettingsSerializer,
)
@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAdminUser])
def app_settings(request):
    config = AppSettings.load()

    if request.method == "GET":
        return Response({"data": AppSettingsSerializer(config).data})

    previous_ranges = config.effective_scan_ranges
    serializer = AppSettingsSerializer(config, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    ranges_changed = previous_ranges != config.effective_scan_ranges
    devices_removed_from_monitoring = 0
    if ranges_changed:
        devices_removed_from_monitoring = mark_devices_outside_scan_ranges_offline(
            previous_ranges,
            config.effective_scan_ranges,
        )
    message = "Scanner, notification, and integration settings were updated."
    if devices_removed_from_monitoring:
        message += (
            f" {devices_removed_from_monitoring} device"
            f"{'s were' if devices_removed_from_monitoring != 1 else ' was'} marked offline "
            "because the configured ranges no longer include them."
        )
    return success_response(
        AppSettingsSerializer(config).data,
        "Settings saved",
        message,
    )
