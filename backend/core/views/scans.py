import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..access_control import CanRunScans, user_capabilities
from ..datetime_utils import utc_isoformat
from ..models import AppSettings, DockerHost, NetworkEvent, ScanRun
from ..scan import ScanAlreadyRunning, active_scan_run, scan, validate_ip_ranges
from ..serializers import ScanRunSerializer
from ..user_messages import error_response, scan_error_message, success_response
from .devices import active_device_counters

LOGGER = logging.getLogger(__name__)


def reconcile_scan_status(latest_scan, active_scan):
    if not latest_scan or not active_scan:
        return active_scan

    latest_finished_at = latest_scan.finished_at or latest_scan.started_at
    if latest_finished_at <= active_scan.started_at:
        return active_scan

    active_scan.status = ScanRun.Status.FAILED
    active_scan.finished_at = latest_finished_at
    active_scan.error = "Scan was superseded by a newer completed scan."
    active_scan.failure_code = "superseded_scan"
    active_scan.failure_type = "InterruptedScan"
    active_scan.failure_stage = "heartbeat"
    active_scan.failure_fingerprint = "superseded-scan"
    active_scan.save(
        update_fields=[
            "status",
            "finished_at",
            "error",
            "failure_code",
            "failure_type",
            "failure_stage",
            "failure_fingerprint",
        ]
    )
    return None


@extend_schema(
    request=inline_serializer(
        name="ScanNowRequest",
        fields={
            "ip_range": serializers.CharField(required=False),
            "scan_ranges": serializers.ListField(
                child=serializers.CharField(),
                required=False,
            ),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanRunScans])
def scan_now(request):
    config = AppSettings.load()
    requested_ranges = request.data.get("scan_ranges")
    error_field = "scan_ranges"
    if requested_ranges is None:
        requested_ranges = request.data.get("ip_range")
        if requested_ranges is not None:
            error_field = "ip_range"
    if requested_ranges is None:
        requested_ranges = config.effective_scan_ranges
    try:
        scan_ranges = validate_ip_ranges(requested_ranges)
    except ValueError as exc:
        raise ValidationError({error_field: str(exc)}) from exc

    try:
        scan_run = scan(scan_ranges, source=ScanRun.Source.MANUAL)
    except ScanAlreadyRunning as exc:
        active_scan = exc.active_scan
        message = str(exc)
        return error_response(
            "Scan already running",
            message,
            response_status=status.HTTP_409_CONFLICT,
            data=ScanRunSerializer(active_scan).data if active_scan else None,
            status="Conflict",
            info=message,
        )
    except Exception as exc:
        LOGGER.exception("Scan failed for %s", scan_ranges)
        failed_scan = ScanRun.objects.filter(ip_range=scan_ranges[0]).first()
        message = scan_error_message(exc)
        return error_response(
            "Scan failed",
            message,
            response_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            data=ScanRunSerializer(failed_scan).data if failed_scan else None,
            status="Error",
            info=message,
        )

    return success_response(
        ScanRunSerializer(scan_run).data,
        "Scan completed",
        "LanGuard finished scanning the configured network ranges.",
        response_status=status.HTTP_202_ACCEPTED,
        status="OK",
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def scan_status(request):
    active_scan = active_scan_run()
    latest_scan = ScanRun.objects.exclude(status=ScanRun.Status.RUNNING).first()
    active_scan = reconcile_scan_status(latest_scan, active_scan)
    visible_scan = active_scan or latest_scan
    app_config = AppSettings.load()
    now = timezone.now()
    duration_seconds = None
    if visible_scan:
        finished_at = visible_scan.finished_at or now
        duration_seconds = max(
            0,
            int((finished_at - visible_scan.started_at).total_seconds()),
        )
    return Response(
        {
            "data": ScanRunSerializer(latest_scan).data if latest_scan else None,
            "active_scan": ScanRunSerializer(active_scan).data if active_scan else None,
            "visibility": {
                "is_scanning": active_scan is not None,
                "source": active_scan.source if active_scan else "",
                "current_range": visible_scan.ip_range if visible_scan else "",
                "current_ranges": (
                    visible_scan.scan_ranges or [visible_scan.ip_range]
                    if visible_scan
                    else []
                ),
                "current_range_labels": (
                    visible_scan.scan_range_labels if visible_scan else {}
                ),
                "started_at": (
                    utc_isoformat(visible_scan.started_at) if visible_scan else None
                ),
                "finished_at": (
                    utc_isoformat(visible_scan.finished_at) if visible_scan else None
                ),
                "duration_seconds": duration_seconds,
                "last_error": (
                    visible_scan.error if visible_scan and visible_scan.error else ""
                ),
            },
            "time_zone": app_config.time_zone,
            "network_ranges": app_config.effective_scan_ranges,
            "network_range_labels": app_config.effective_scan_range_labels,
            "integrations": {
                "adguard": {
                    "enabled": app_config.adguard_enabled,
                    "configured": bool(
                        app_config.adguard_url
                        and (
                            not app_config.adguard_username
                            or app_config.adguard_password
                        )
                    ),
                },
                "pihole": {
                    "enabled": app_config.pihole_enabled,
                    "configured": bool(
                        app_config.pihole_url and app_config.pihole_password
                    ),
                },
                "speedtest_tracker": {
                    "enabled": app_config.speedtest_tracker_enabled,
                    "configured": bool(
                        app_config.speedtest_tracker_url
                        and app_config.speedtest_tracker_api_token
                    ),
                },
                "homebox": {
                    "enabled": app_config.homebox_enabled,
                    "configured": bool(
                        app_config.homebox_url and app_config.homebox_api_token
                    ),
                },
                "docker": {
                    "configured": DockerHost.objects.exists(),
                },
            },
            "permissions": user_capabilities(request.user),
            "counters": {
                **active_device_counters(),
                "unnotified_events": NetworkEvent.objects.filter(notified=False).count(),
            },
        },
        status=status.HTTP_200_OK,
    )
