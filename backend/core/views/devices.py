import ipaddress
import logging
from datetime import timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..access_control import CanEditDevices, CanRunScans
from ..api import paginated_payload, parse_bool_param, parse_int_param
from ..datetime_utils import utc_isoformat
from ..models import AppSettings, Device, DevicePort, NetworkEvent
from ..scan import detect_web_interface
from ..serializers.devices import (
    DeviceBulkUpdateSerializer,
    DeviceSerializer,
    device_needs_attention,
    device_risk_signature,
)
from ..user_messages import error_response, success_response
from ..wake_on_lan import send_magic_packet, wake_broadcast_address
LOGGER = logging.getLogger(__name__)

DEVICE_ORDERING_FIELDS = {
    "name": ("name", "ip", "id"),
    "-name": ("-name", "ip", "id"),
    "firstseen": ("firstseen", "ip", "id"),
    "-firstseen": ("-firstseen", "ip", "id"),
    "lastseen": ("lastseen", "ip", "id"),
    "-lastseen": ("-lastseen", "ip", "id"),
}
FIRST_SEEN_PERIODS = {"today", "7d", "30d"}
OUTSIDE_NETWORK_RANGE_FILTER = "outside"
DEVICE_AVAILABILITY_PERIODS = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}
PRESENCE_EVENT_STATUSES = {
    NetworkEvent.EventType.NEW_DEVICE: "online",
    NetworkEvent.EventType.DEVICE_ONLINE: "online",
    NetworkEvent.EventType.DEVICE_OFFLINE: "offline",
}


def first_seen_threshold(period):
    now = timezone.now()
    if period == "today":
        config = AppSettings.load()
        try:
            app_timezone = ZoneInfo(config.time_zone)
        except ZoneInfoNotFoundError:
            app_timezone = timezone.get_current_timezone()
        if timezone.is_naive(now):
            now = timezone.make_aware(now, datetime_timezone.utc)
        local_now = timezone.localtime(now, app_timezone)
        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        if not settings.USE_TZ:
            return timezone.make_naive(local_midnight, datetime_timezone.utc)
        return local_midnight
    days = 7 if period == "7d" else 30
    return now - timedelta(days=days)


def ip_sort_key(device_item):
    try:
        address = ipaddress.ip_address(device_item.ip)
    except ValueError:
        return (1, device_item.ip, device_item.name.lower(), device_item.id)
    return (
        0,
        address.version,
        int(address),
        device_item.name.lower(),
        device_item.id,
    )


def filter_devices_by_network_ranges(devices, raw_filter):
    if not raw_filter:
        return devices

    requested_ranges = list(
        dict.fromkeys(value.strip() for value in raw_filter.split(",") if value.strip())
    )
    configured_ranges = AppSettings.load().effective_scan_ranges
    allowed_values = set(configured_ranges) | {OUTSIDE_NETWORK_RANGE_FILTER}
    if not requested_ranges or any(value not in allowed_values for value in requested_ranges):
        raise ValidationError(
            {
                "network_ranges": (
                    "Choose one or more configured network ranges, or Outside "
                    "configured ranges."
                )
            }
        )

    configured_networks = [
        ipaddress.ip_network(network_range, strict=False)
        for network_range in configured_ranges
    ]
    selected_networks = [
        ipaddress.ip_network(network_range, strict=False)
        for network_range in requested_ranges
        if network_range != OUTSIDE_NETWORK_RANGE_FILTER
    ]
    include_outside = OUTSIDE_NETWORK_RANGE_FILTER in requested_ranges
    matching_ids = []
    for device_id, ip_value in devices.values_list("id", "ip"):
        try:
            address = ipaddress.ip_address(ip_value)
        except ValueError:
            if include_outside:
                matching_ids.append(device_id)
            continue
        in_selected_range = any(address in network for network in selected_networks)
        outside_configured_ranges = not any(
            address in network for network in configured_networks
        )
        if in_selected_range or (include_outside and outside_configured_ranges):
            matching_ids.append(device_id)

    return devices.filter(id__in=matching_ids)


def paginated_device_payload(request, devices):
    ordering = request.query_params.get("ordering")
    if ordering in DEVICE_ORDERING_FIELDS:
        devices = devices.order_by(*DEVICE_ORDERING_FIELDS[ordering])
        return paginated_payload(
            request,
            devices,
            DeviceSerializer,
            default_limit=10,
            max_limit=100,
        )
    if ordering in {"ip", "-ip"}:
        limit = parse_int_param(
            request.query_params,
            "limit",
            default=10,
            minimum=1,
            maximum=100,
        )
        offset = parse_int_param(
            request.query_params,
            "offset",
            default=0,
            minimum=0,
        )
        sorted_devices = sorted(
            devices,
            key=ip_sort_key,
            reverse=ordering == "-ip",
        )
        total = len(sorted_devices)
        next_offset = offset + limit if offset + limit < total else None
        previous_offset = max(offset - limit, 0) if offset > 0 else None
        return {
            "data": DeviceSerializer(
                sorted_devices[offset : offset + limit], many=True
            ).data,
            "pagination": {
                "count": total,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset,
                "previous_offset": previous_offset,
            },
        }
    if ordering:
        raise ValidationError(
            {
                "ordering": (
                    "Must be one of: name, -name, ip, -ip, firstseen, "
                    "-firstseen, lastseen, -lastseen."
                )
            }
        )
    return paginated_payload(
        request,
        devices,
        DeviceSerializer,
        default_limit=10,
        max_limit=100,
    )


def append_availability_segment(segments, state, started_at, ended_at):
    duration_seconds = max((ended_at - started_at).total_seconds(), 0)
    if duration_seconds <= 0:
        return
    if segments and segments[-1]["status"] == state:
        segments[-1]["ended_at"] = utc_isoformat(ended_at)
        segments[-1]["duration_seconds"] += duration_seconds
        return
    segments.append(
        {
            "status": state,
            "started_at": utc_isoformat(started_at),
            "ended_at": utc_isoformat(ended_at),
            "duration_seconds": duration_seconds,
        }
    )


def device_availability_payload(device_item, period, now=None):
    now = now or timezone.now()
    started_at = now - DEVICE_AVAILABILITY_PERIODS[period]
    presence_events = device_item.events.filter(
        event_type__in=PRESENCE_EVENT_STATUSES,
        created_at__lte=now,
    )
    previous_event = presence_events.filter(created_at__lte=started_at).first()
    state = (
        PRESENCE_EVENT_STATUSES[previous_event.event_type]
        if previous_event
        else "unknown"
    )
    events = list(
        presence_events.filter(created_at__gt=started_at).order_by("created_at", "id")
    )

    segments = []
    cursor = started_at
    status_changes = 0
    for event in events:
        append_availability_segment(segments, state, cursor, event.created_at)
        state = PRESENCE_EVENT_STATUSES[event.event_type]
        cursor = event.created_at
        if event.event_type != NetworkEvent.EventType.NEW_DEVICE:
            status_changes += 1
    append_availability_segment(segments, state, cursor, now)

    online_seconds = sum(
        segment["duration_seconds"]
        for segment in segments
        if segment["status"] == "online"
    )
    offline_seconds = sum(
        segment["duration_seconds"]
        for segment in segments
        if segment["status"] == "offline"
    )
    tracked_seconds = online_seconds + offline_seconds
    total_seconds = max((now - started_at).total_seconds(), 1)

    return {
        "period": period,
        "started_at": utc_isoformat(started_at),
        "ended_at": utc_isoformat(now),
        "availability_percent": (
            round((online_seconds / tracked_seconds) * 100, 1)
            if tracked_seconds
            else None
        ),
        "coverage_percent": round((tracked_seconds / total_seconds) * 100, 1),
        "online_seconds": round(online_seconds),
        "offline_seconds": round(offline_seconds),
        "status_changes": status_changes,
        "segments": segments,
    }


def active_device_counters():
    active_devices = Device.objects.filter(archived=False)
    regular_devices = active_devices.filter(is_visitor=False)
    visitor_devices = active_devices.filter(is_visitor=True)
    return {
        "all_devices": regular_devices.count(),
        "online_devices": regular_devices.exclude(status=Device.Status.OFFLINE).count(),
        "offline_devices": regular_devices.filter(status=Device.Status.OFFLINE).count(),
        "new_devices": regular_devices.filter(known=False).count(),
        "open_ports": DevicePort.objects.filter(
            open=True,
            device__archived=False,
        ).count(),
        "visitor_devices": visitor_devices.count(),
        "online_visitors": visitor_devices.exclude(status=Device.Status.OFFLINE).count(),
        "archived_devices": Device.objects.filter(archived=True).count(),
    }


@extend_schema(methods=["GET"], responses=OpenApiTypes.OBJECT)
@extend_schema(
    methods=["PUT"],
    request=DeviceSerializer,
    responses=OpenApiTypes.OBJECT,
)
@extend_schema(methods=["DELETE"], responses=OpenApiTypes.OBJECT)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def device(request):
    counters = active_device_counters()

    if request.method == "GET":
        id_ = request.query_params.get("id")
        if not id_:
            archived = parse_bool_param(request.query_params, "archived") is True
            devices = Device.objects.prefetch_related("ports").filter(archived=archived)
            online = parse_bool_param(request.query_params, "online")
            device_status = request.query_params.get("status")
            known = parse_bool_param(request.query_params, "known")
            is_visitor = parse_bool_param(request.query_params, "is_visitor")
            search = request.query_params.get("search")
            open_port = request.query_params.get("open_port")
            first_seen = request.query_params.get("first_seen")
            network_ranges = request.query_params.get("network_ranges")
            homebox_linked = parse_bool_param(request.query_params, "homebox_linked")
            needs_attention = parse_bool_param(request.query_params, "needs_attention")

            if device_status:
                if device_status not in Device.Status.values:
                    raise ValidationError({"status": "Invalid device status."})
                devices = devices.filter(status=device_status)
            elif online is not None:
                devices = devices.filter(online=online)
            if known is not None:
                devices = devices.filter(known=known)
            if is_visitor is not None:
                devices = devices.filter(is_visitor=is_visitor)
            if search:
                devices = devices.filter(
                    Q(name__icontains=search)
                    | Q(ip__icontains=search)
                    | Q(mac__icontains=search)
                    | Q(hostname__icontains=search)
                    | Q(vendor__icontains=search)
                )
            if open_port:
                port = parse_int_param(
                    request.query_params,
                    "open_port",
                    default=open_port,
                    minimum=1,
                    maximum=65535,
                )
                devices = devices.filter(ports__port=port, ports__open=True).distinct()
            if first_seen:
                if first_seen not in FIRST_SEEN_PERIODS:
                    raise ValidationError(
                        {"first_seen": "Must be one of: today, 7d, 30d."}
                    )
                devices = devices.filter(
                    firstseen__gte=first_seen_threshold(first_seen)
                )
            if homebox_linked is not None:
                devices = devices.filter(homebox_item_id__isnull=not homebox_linked)
            devices = filter_devices_by_network_ranges(devices, network_ranges)
            if needs_attention is not None:
                attention_ids = [
                    item.id for item in devices if device_needs_attention(item)
                ]
                if needs_attention:
                    devices = devices.filter(id__in=attention_ids)
                else:
                    devices = devices.exclude(id__in=attention_ids)

            payload = paginated_device_payload(request, devices)
            return Response(
                {
                    "data": payload["data"],
                    "counters": counters,
                    "pagination": payload["pagination"],
                },
                status=status.HTTP_200_OK,
            )

        device_item = get_object_or_404(Device, pk=id_)
        return Response(
            {"data": DeviceSerializer(device_item).data},
            status=status.HTTP_200_OK,
        )

    id_ = request.query_params.get("id")
    if not id_:
        return Response(
            {"status": "Error", "info": "Id is missing"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    device_item = get_object_or_404(Device, pk=id_)

    if request.method == "PUT":
        serializer = DeviceSerializer(device_item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"status": "Error", "info": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        device_item = serializer.save()
        LOGGER.info(
            "Device (%s) updated - Name: %s / Icon: %s / Known: %s",
            device_item.id,
            device_item.name,
            device_item.icon,
            device_item.known,
        )
        return success_response(
            {"id": device_item.id},
            "Device saved",
            f"{device_item.name} was updated.",
            response_status=status.HTTP_202_ACCEPTED,
            status="OK",
        )

    LOGGER.warning(
        "Device (%s) %s - deleted successfully",
        device_item.id,
        device_item.name,
    )
    device_item.delete()
    return success_response(
        {"id": id_},
        "Device deleted",
        "The device was removed.",
        response_status=status.HTTP_202_ACCEPTED,
        status="OK",
    )


@extend_schema(request=DeviceBulkUpdateSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def bulk_update_devices(request):
    serializer = DeviceBulkUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    device_ids = serializer.validated_data["ids"]
    known = serializer.validated_data.get("known")
    is_visitor = serializer.validated_data.get("is_visitor")
    acknowledge_attention = serializer.validated_data.get("acknowledge_attention")
    devices = Device.objects.prefetch_related("ports").filter(id__in=device_ids)
    found_ids = set(devices.values_list("id", flat=True))
    if len(found_ids) != len(device_ids):
        raise ValidationError(
            {"ids": "One or more selected devices no longer exist. Refresh and try again."}
        )

    if acknowledge_attention:
        known_devices = [item for item in devices if item.known]
        skipped_unknown_count = len(device_ids) - len(known_devices)
        updated_devices = []
        for item in known_devices:
            signature = device_risk_signature(item)
            if item.attention_acknowledged_signature != signature:
                item.attention_acknowledged_signature = signature
                updated_devices.append(item)
        if updated_devices:
            Device.objects.bulk_update(
                updated_devices,
                ["attention_acknowledged_signature"],
            )
        reviewed_count = len(known_devices)
        if reviewed_count:
            message = (
                f"{reviewed_count} selected device"
                f"{'s' if reviewed_count != 1 else ''} marked as reviewed."
            )
        else:
            message = "No devices were marked as reviewed."
        if skipped_unknown_count:
            message += (
                f" {skipped_unknown_count} unknown device"
                f"{'s were' if skipped_unknown_count != 1 else ' was'} skipped; "
                "mark them as known first."
            )
        return success_response(
            {
                "ids": device_ids,
                "acknowledge_attention": True,
                "reviewed_count": reviewed_count,
                "skipped_unknown_count": skipped_unknown_count,
                "updated_count": len(updated_devices),
            },
            "Attention reviewed",
            message,
            status="OK",
        )

    if is_visitor is True:
        update_values = {"known": True, "is_visitor": True}
        state_label = "visitor"
    elif known is True:
        update_values = {"known": True, "is_visitor": False}
        state_label = "known"
    elif known is False:
        update_values = {"known": False, "is_visitor": False}
        state_label = "new"
    else:
        update_values = {"is_visitor": False}
        state_label = "not visitor"
    updated_count = devices.exclude(**update_values).update(**update_values)
    selected_count = len(device_ids)
    return success_response(
        {
            "ids": device_ids,
            "known": known,
            "is_visitor": is_visitor,
            "updated_count": updated_count,
        },
        "Devices updated",
        f"{selected_count} selected device{'s' if selected_count != 1 else ''} marked as {state_label}.",
        status="OK",
    )


@extend_schema(
    request=inline_serializer(
        name="WakeDeviceRequest",
        fields={"id": serializers.IntegerField(min_value=1)},
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanRunScans])
def wake_device(request):
    try:
        device_id = int(request.data.get("id"))
    except (TypeError, ValueError):
        raise ValidationError({"id": "A valid device ID is required."})
    if device_id < 1:
        raise ValidationError({"id": "A valid device ID is required."})

    device_item = get_object_or_404(Device, pk=device_id, archived=False)
    try:
        broadcast_address = wake_broadcast_address(
            device_item.ip,
            AppSettings.load().effective_scan_ranges,
        )
        send_magic_packet(device_item.mac, broadcast_address)
    except ValueError as exc:
        raise ValidationError({"device": str(exc)}) from exc
    except OSError:
        LOGGER.exception(
            "Could not send Wake-on-LAN packet for device %s", device_item.id
        )
        return error_response(
            "Wake request failed",
            "LanGuard could not send the Wake-on-LAN packet. Check the host network configuration.",
            response_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    LOGGER.info("Wake-on-LAN packet sent for device %s", device_item.id)
    return success_response(
        {"id": device_item.id},
        "Wake request sent",
        f"Wake-on-LAN packet sent to {device_item.name}.",
        response_status=status.HTTP_202_ACCEPTED,
        status="OK",
    )


@extend_schema(
    responses=inline_serializer(
        name="DeviceWebInterfaceResponse",
        fields={"url": serializers.URLField(allow_blank=True)},
    )
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def device_web_interface(request):
    id_ = request.query_params.get("id")
    if not id_:
        raise ValidationError({"id": "Device id is required."})
    target = get_object_or_404(Device.objects.prefetch_related("ports"), pk=id_)
    open_ports = list(target.ports.filter(open=True).values_list("port", flat=True))
    return Response(
        {"url": detect_web_interface(target.ip, open_ports)},
        status=status.HTTP_200_OK,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def device_availability(request):
    device_id = parse_int_param(request.query_params, "device", 0, 1)
    period = request.query_params.get("period", "week")
    if period not in DEVICE_AVAILABILITY_PERIODS:
        raise ValidationError({"period": "Must be one of: day, week, month, year."})
    device_item = get_object_or_404(Device, id=device_id)
    return Response(
        {"status": "OK", "data": device_availability_payload(device_item, period)}
    )
