from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError

from ..api import paginated_response, parse_bool_param, parse_datetime_param, parse_int_param
from ..models import NetworkEvent, ScanRun
from ..serializers import NetworkEventSerializer, ScanRunSerializer


@extend_schema(responses=ScanRunSerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def scan_runs(request):
    runs = ScanRun.objects.all()
    scan_status = request.query_params.get("status")
    ip_range = request.query_params.get("ip_range")
    started_after = parse_datetime_param(request.query_params, "started_after")
    started_before = parse_datetime_param(request.query_params, "started_before")

    if scan_status:
        if scan_status not in ScanRun.Status.values:
            raise ValidationError({"status": "Invalid scan status."})
        runs = runs.filter(status=scan_status)
    if ip_range:
        runs = runs.filter(ip_range=ip_range)
    if started_after:
        runs = runs.filter(started_at__gte=started_after)
    if started_before:
        runs = runs.filter(started_at__lte=started_before)

    return paginated_response(
        request,
        runs,
        ScanRunSerializer,
        default_limit=25,
        max_limit=500,
    )


@extend_schema(responses=NetworkEventSerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def events(request):
    event_type = request.query_params.get("event_type")
    notified = parse_bool_param(request.query_params, "notified")
    created_after = parse_datetime_param(request.query_params, "created_after")
    created_before = parse_datetime_param(request.query_params, "created_before")
    device_id = request.query_params.get("device")
    scan_run_id = request.query_params.get("scan_run")

    queryset = NetworkEvent.objects.select_related("device", "device_port", "scan_run")
    if event_type:
        if event_type not in NetworkEvent.EventType.values:
            raise ValidationError({"event_type": "Invalid event type."})
        queryset = queryset.filter(event_type=event_type)
    if notified is not None:
        queryset = queryset.filter(notified=notified)
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)
    if device_id:
        queryset = queryset.filter(
            device_id=parse_int_param(request.query_params, "device", 0, 1)
        )
    if scan_run_id:
        queryset = queryset.filter(
            scan_run_id=parse_int_param(request.query_params, "scan_run", 0, 1)
        )

    return paginated_response(
        request,
        queryset,
        NetworkEventSerializer,
        default_limit=50,
        max_limit=500,
    )
