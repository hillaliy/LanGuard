from django.conf import settings
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..access_control import CanEditDevicesOrRunScans
from ..detailed_port_scans import parse_port_specification
from ..models import DetailedPortScan, Device
from ..serializers.scans import DetailedPortScanSerializer
from ..user_messages import error_response, success_response


@extend_schema(
    request=inline_serializer(
        name="DetailedPortScanRequest",
        fields={
            "device": serializers.IntegerField(min_value=1),
            "ports": serializers.CharField(),
        },
    ),
    responses=DetailedPortScanSerializer,
)
@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevicesOrRunScans])
def detailed_port_scan(request):
    if request.method == "GET":
        try:
            device_id = int(request.query_params.get("device"))
        except (TypeError, ValueError):
            raise ValidationError({"device": "A valid device ID is required."})
        if device_id < 1:
            raise ValidationError({"device": "A valid device ID is required."})
        job = (
            DetailedPortScan.objects.filter(device_id=device_id)
            .select_related("device", "requested_by")
            .first()
        )
        return Response(
            {"data": DetailedPortScanSerializer(job).data if job else None},
            status=status.HTTP_200_OK,
        )

    try:
        device_id = int(request.data.get("device"))
    except (TypeError, ValueError):
        raise ValidationError({"device": "A valid device ID is required."})
    if device_id < 1:
        raise ValidationError({"device": "A valid device ID is required."})
    device = get_object_or_404(Device, pk=device_id, archived=False)
    if device.status != Device.Status.ONLINE:
        return error_response(
            "Device is not online",
            "Detailed port scans are only available while the device is online.",
            response_status=status.HTTP_409_CONFLICT,
        )
    try:
        ports = parse_port_specification(request.data.get("ports"))
    except ValueError as exc:
        raise ValidationError({"ports": str(exc)}) from exc

    active_statuses = [
        DetailedPortScan.Status.QUEUED,
        DetailedPortScan.Status.RUNNING,
    ]
    if DetailedPortScan.objects.filter(
        device=device,
        status__in=active_statuses,
    ).exists():
        return error_response(
            "Scan already active",
            "This device already has a detailed port scan queued or running.",
            response_status=status.HTTP_409_CONFLICT,
        )
    if (
        DetailedPortScan.objects.filter(status__in=active_statuses).count()
        >= settings.DETAILED_PORT_SCAN_MAX_QUEUED
    ):
        return error_response(
            "Scan queue is full",
            "Wait for an active detailed port scan to finish, then try again.",
            response_status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        job = DetailedPortScan.objects.create(
            device=device,
            requested_by=request.user,
            ports=ports,
            total_ports=len(ports),
        )
    except IntegrityError:
        return error_response(
            "Scan already active",
            "This device already has a detailed port scan queued or running.",
            response_status=status.HTTP_409_CONFLICT,
        )
    return success_response(
        DetailedPortScanSerializer(job).data,
        "Detailed scan queued",
        f"LanGuard queued {len(ports)} TCP ports for {device.name}.",
        response_status=status.HTTP_202_ACCEPTED,
        status="OK",
    )


@extend_schema(
    request=inline_serializer(
        name="CancelDetailedPortScanRequest",
        fields={"id": serializers.IntegerField(min_value=1)},
    ),
    responses=DetailedPortScanSerializer,
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevicesOrRunScans])
def cancel_detailed_port_scan(request):
    try:
        job_id = int(request.data.get("id"))
    except (TypeError, ValueError):
        raise ValidationError({"id": "A valid detailed scan ID is required."})
    if job_id < 1:
        raise ValidationError({"id": "A valid detailed scan ID is required."})
    job = get_object_or_404(
        DetailedPortScan.objects.select_related("device", "requested_by"),
        pk=job_id,
    )
    if job.status == DetailedPortScan.Status.QUEUED:
        job.status = DetailedPortScan.Status.CANCELLED
        job.cancel_requested = True
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "cancel_requested", "finished_at"])
    elif job.status == DetailedPortScan.Status.RUNNING:
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested"])
    else:
        return error_response(
            "Scan already finished",
            "Only queued or running detailed scans can be cancelled.",
            response_status=status.HTTP_409_CONFLICT,
        )
    return success_response(
        DetailedPortScanSerializer(job).data,
        "Cancellation requested",
        "LanGuard will stop the detailed port scan safely.",
        response_status=status.HTTP_202_ACCEPTED,
        status="OK",
    )
