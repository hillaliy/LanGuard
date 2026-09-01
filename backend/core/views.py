import ipaddress
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import status, generics, permissions
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import DatabaseError, IntegrityError, connection
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

import logging
import requests

from django.utils import timezone
from .datetime_utils import utc_isoformat
from .maintenance import cleanup_activity
from .serializers import (
    AdGuardUnmatchedClientSerializer,
    AdGuardConnectionSerializer,
    AppSettingsSerializer,
    DeviceDNSActivitySerializer,
    DeviceSerializer,
    GlobalDNSActivitySerializer,
    HomeMapLayoutSerializer,
    NetworkEventSerializer,
    NotificationDeliverySerializer,
    NotificationTestSerializer,
    ScanRunSerializer,
    UserManagementSerializer,
    UserSerializer,
    device_attention_acknowledged,
    device_risk,
    device_risk_signature,
)
from .models import (
    AdGuardUnmatchedClient,
    AppSettings,
    Device,
    DeviceDNSActivity,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)
from .api import (
    paginated_response,
    paginated_payload,
    parse_bool_param,
    parse_datetime_param,
    parse_int_param,
)
from .scan import detect_web_interface, scan, validate_ip_range
from .notifications import send_discord_test, send_telegram_test
from .adguard import AdGuardError, sync_adguard_query_log, test_adguard_connection
from .diagnostics import build_diagnostics_report
from .user_messages import error_response, scan_error_message, success_response

LOGGER = logging.getLogger(__name__)

INVENTORY_FORMAT = "languard-device-inventory"

DOCKER_TO_MAC_ICON_ALIASES = {
    "unknown": "questionmark.circle",
    "desktop": "desktopcomputer",
    "router": "wifi.router",
    "smart-hub": "point.3.connected.trianglepath.dotted",
    "phone": "iphone",
    "tablet": "ipad",
    "smart-watch": "applewatch",
    "laptop": "macbook",
    "tv": "tv",
    "streamer": "airplayvideo",
    "security-camera": "camera",
    "shutter": "window.shade.closed",
    "blinds": "blinds.horizontal.closed",
    "light": "lightbulb",
    "led-strip": "light.strip.2",
    "desk-lamp": "lamp.desk",
    "ceiling-light": "lamp.ceiling",
    "air-conditioner": "air.conditioner.horizontal",
    "fan": "fan",
    "ceiling-fan": "fan.ceiling",
    "thermostat": "thermometer.medium",
    "speaker": "homepod",
    "printer": "printer",
    "lock": "lock",
    "robot-vacuum": "robotic.vacuum",
    "power-strip": "poweroutlet.strip",
    "server": "server.rack",
}
DOCKER_ICON_VALUES = set(DOCKER_TO_MAC_ICON_ALIASES)
MAC_TO_DOCKER_ICON_ALIASES = {
    **{value: key for key, value in DOCKER_TO_MAC_ICON_ALIASES.items()},
    "airplayvideo": "streamer",
    "blinds.horizontal.closed": "shutter",
    "cpu": "smart-hub",
    "hifispeaker": "speaker",
    "lamp.ceiling": "ceiling-light",
    "light.panel": "light",
    "light.recessed": "ceiling-light",
    "lightbulb.max": "light",
    "lightswitch.on": "light",
    "point.3.connected.trianglepath.dotted": "smart-hub",
    "poweroutlet.type.h": "power-strip",
    "powerplug": "power-strip",
    "sensor.tag.radiowaves.forward": "smart-hub",
    "switch.2": "smart-hub",
    "video.doorbell": "security-camera",
    "window.shade.closed": "blinds",
}


def export_inventory_icon(icon):
    value = str(icon or "").strip()
    return DOCKER_TO_MAC_ICON_ALIASES.get(value, value)


def import_inventory_icon(icon, fallback="unknown"):
    value = str(icon or "").strip()
    normalized = MAC_TO_DOCKER_ICON_ALIASES.get(value, value)
    if normalized in DOCKER_ICON_VALUES:
        return normalized
    return fallback


INVENTORY_ROOM_FIELDS = ("room", "roomName", "room_name", "deviceRoom", "device_room")
INVENTORY_ROLE_FIELDS = ("role", "deviceRole", "device_role", "effectiveRole", "effective_role")


def import_inventory_room(item):
    for field in INVENTORY_ROOM_FIELDS:
        if field in item:
            return str(item.get(field) or "").strip()[:100]
    return None


def import_inventory_role(item):
    for field in INVENTORY_ROLE_FIELDS:
        if field in item:
            return str(item.get(field) or "").strip()[:32]
    return None


DEVICE_ORDERING_FIELDS = {
    "name": ("name", "ip", "id"),
    "-name": ("-name", "ip", "id"),
    "firstseen": ("firstseen", "ip", "id"),
    "-firstseen": ("-firstseen", "ip", "id"),
    "lastseen": ("lastseen", "ip", "id"),
    "-lastseen": ("-lastseen", "ip", "id"),
}
FIRST_SEEN_PERIODS = {"today", "7d", "30d"}


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_status(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        LOGGER.exception("Database health check failed")
        return Response(
            {"status": "unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response({"status": "ok"}, status=status.HTTP_200_OK)


def first_seen_threshold(period):
    now = timezone.now()
    if period == "today":
        config = AppSettings.load()
        try:
            app_timezone = ZoneInfo(config.time_zone)
        except ZoneInfoNotFoundError:
            app_timezone = timezone.get_current_timezone()
        local_now = timezone.localtime(now, app_timezone)
        return local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = 7 if period == "7d" else 30
    return now - timedelta(days=days)


def ip_sort_key(device):
    try:
        address = ipaddress.ip_address(device.ip)
    except ValueError:
        return (1, device.ip, device.name.lower(), device.id)
    return (0, address.version, int(address), device.name.lower(), device.id)


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
        limit = parse_int_param(request.query_params, "limit", default=10, minimum=1, maximum=100)
        offset = parse_int_param(request.query_params, "offset", default=0, minimum=0)
        sorted_devices = sorted(devices, key=ip_sort_key, reverse=ordering == "-ip")
        total = len(sorted_devices)
        next_offset = offset + limit if offset + limit < total else None
        previous_offset = max(offset - limit, 0) if offset > 0 else None
        return {
            "data": DeviceSerializer(sorted_devices[offset : offset + limit], many=True).data,
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


def auth_payload(user, token, *, account_created=False):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "token": token.key,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "notification": {
            "title": "Account created" if account_created else "Signed in",
            "message": "Your LanGuard session is ready.",
        },
    }


def active_staff_count():
    return User.objects.filter(is_active=True, is_staff=True).count()


def staff_count():
    return User.objects.filter(is_staff=True).count()


def reconcile_scan_status(latest_scan, active_scan):
    if not latest_scan or not active_scan:
        return active_scan

    latest_finished_at = latest_scan.finished_at or latest_scan.started_at
    if latest_finished_at <= active_scan.started_at:
        return active_scan

    active_scan.status = ScanRun.Status.FAILED
    active_scan.finished_at = latest_finished_at
    active_scan.error = "Scan was superseded by a newer completed scan."
    active_scan.save(update_fields=["status", "finished_at", "error"])
    return None


def fetch_latest_version():
    if not settings.LATEST_VERSION_URL:
        return None

    request = urllib.request.Request(
        settings.LATEST_VERSION_URL,
        headers={"User-Agent": "LanGuard"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.VERSION_CHECK_TIMEOUT,
        ) as response:
            response_text = response.read().decode("utf-8").strip()
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        UnicodeDecodeError,
    ) as exc:
        LOGGER.info("Latest version check failed: %s", exc)
        return None

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        latest_version = response_text
    else:
        latest_version = payload.get("version") if isinstance(payload, dict) else None

    if isinstance(latest_version, str) and latest_version.strip():
        return latest_version.strip()
    return None


def inventory_device_payload(device):
    risk_data = device_risk(device)
    return {
        "name": device.name,
        "ip": device.ip,
        "mac": device.mac,
        "vendor": device.vendor,
        "vendor_source": device.vendor_source,
        "hostname": getattr(device, "hostname", ""),
        "hostname_source": device.hostname_source,
        "icon": export_inventory_icon(device.icon),
        "secondary_icon": export_inventory_icon(getattr(device, "secondary_icon", "")),
        "role": getattr(device, "role", "") or ("gateway" if device.is_gateway else "device"),
        "room": getattr(device, "room", ""),
        "comments": device.comments,
        "external_url": device.external_url,
        "risk": risk_data["level"],
        "attention_acknowledged": device_attention_acknowledged(device, risk_data),
        "known": device.known,
        "is_gateway": device.is_gateway,
        "status": device.status,
        "open_ports": list(
            device.ports.filter(open=True).order_by("port").values_list("port", flat=True)
        ),
        "first_seen": utc_isoformat(device.firstseen),
        "last_seen": utc_isoformat(device.lastseen),
    }


SWIFT_REFERENCE_DATE_OFFSET = 978307200


def normalize_inventory_mac(value):
    normalized = str(value or "").strip().lower().replace("-", ":")
    parts = normalized.split(":")
    if len(parts) != 6 or any(len(part) != 2 for part in parts):
        return ""
    try:
        if any(int(part, 16) > 255 for part in parts):
            return ""
    except ValueError:
        return ""
    return ":".join(parts)


def inventory_mac_is_locally_administered(mac):
    try:
        first_octet = int(str(mac).split(":")[0], 16)
    except (IndexError, TypeError, ValueError):
        return False
    return bool(first_octet & 0x02)


def should_remove_import_ip_duplicate(device):
    if device.is_gateway:
        return False
    if not device.known:
        return True
    if inventory_mac_is_locally_administered(device.mac):
        return True
    return device.status != Device.Status.ONLINE or not device.online


def parse_inventory_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return bool(value) if value is not None else default


def parse_inventory_datetime(value, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = datetime.fromtimestamp(
                float(value) + SWIFT_REFERENCE_DATE_OFFSET,
                tz=datetime_timezone.utc,
            )
        except (OverflowError, OSError, TypeError, ValueError):
            return fallback
    else:
        parsed = parse_datetime(str(value))
    if parsed is None:
        return fallback
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    if not settings.USE_TZ:
        return timezone.make_naive(parsed, datetime_timezone.utc)
    return parsed


def normalize_inventory_ports(raw_ports):
    ports = []
    for raw_port in raw_ports or []:
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            raise ValidationError({"open_ports": "Ports must be numbers."}) from None
        if port < 1 or port > 65535:
            raise ValidationError({"open_ports": "Ports must be between 1 and 65535."})
        ports.append(port)
    return sorted(set(ports))


def inventory_devices_from_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValidationError({"detail": "Import file must be a JSON object or device list."})

    if payload.get("format") and payload.get("format") != INVENTORY_FORMAT:
        raise ValidationError({"format": "Unsupported inventory format."})

    devices = payload.get("devices")
    if not isinstance(devices, list):
        raise ValidationError({"devices": "Import file must include a devices list."})
    return devices


def watchyourlan_devices_from_payload(payload):
    if isinstance(payload, list):
        hosts = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        hosts = payload["data"]
    else:
        raise ValidationError(
            {
                "detail": (
                    "Choose a WatchYourLAN JSON file downloaded from the /api/all endpoint."
                )
            }
        )

    if hosts and not any(
        isinstance(host, dict) and ("Mac" in host or "IP" in host)
        for host in hosts
    ):
        raise ValidationError(
            {
                "detail": (
                    "The selected file does not contain WatchYourLAN /api/all records."
                )
            }
        )

    devices = []
    for host in hosts:
        if not isinstance(host, dict):
            devices.append(host)
            continue

        name = host.get("Name")
        hostname = host.get("DNS")
        ip = host.get("IP")
        mac = host.get("Mac")
        vendor = host.get("Hw")
        known = host.get("Known", 0)
        online = parse_inventory_bool(host.get("Now", 0))
        last_seen = host.get("Date")

        devices.append(
            {
                "name": name or hostname or "Device",
                "hostname": hostname or "",
                "hostname_source": Device.IdentitySource.IMPORTED if hostname else "",
                "ip": ip,
                "mac": mac,
                "vendor": vendor or "",
                "vendor_source": Device.IdentitySource.IMPORTED if vendor else "",
                "known": parse_inventory_bool(known),
                "status": Device.Status.ONLINE if online else Device.Status.OFFLINE,
                "first_seen": last_seen,
                "last_seen": last_seen,
            }
        )

    return {
        "format": INVENTORY_FORMAT,
        "version": 1,
        "devices": devices,
    }


def import_inventory_devices(payload):
    imported_devices = inventory_devices_from_payload(payload)
    created = 0
    updated = 0
    skipped = 0
    removed_duplicates = 0
    now = timezone.now()

    for item in imported_devices:
        if not isinstance(item, dict):
            skipped += 1
            continue

        mac = normalize_inventory_mac(item.get("mac") or item.get("macAddress"))
        ip = str(item.get("ip") or item.get("ipAddress") or "").strip()
        if not mac or not ip:
            skipped += 1
            continue

        try:
            ipaddress.ip_address(ip)
        except ValueError:
            skipped += 1
            continue

        name = str(item.get("name") or "Device").strip()[:100] or "Device"
        hostname = str(item.get("hostname") or item.get("hostName") or "").strip()[:255]
        hostname_source = str(
            item.get("hostname_source") or item.get("hostnameSource") or ""
        ).strip()
        vendor_source = str(
            item.get("vendor_source") or item.get("vendorSource") or ""
        ).strip()
        valid_identity_sources = set(Device.IdentitySource.values)
        if hostname_source not in valid_identity_sources:
            hostname_source = Device.IdentitySource.IMPORTED if hostname else ""
        imported_vendor = str(item.get("vendor") or "").strip()[:255]
        if vendor_source not in valid_identity_sources:
            vendor_source = Device.IdentitySource.IMPORTED if imported_vendor else ""
        comments_present = "comments" in item
        comments = str(item.get("comments") or "").strip()
        external_url_present = "external_url" in item or "externalUrl" in item
        external_url = str(item.get("external_url") or item.get("externalUrl") or "").strip()
        if external_url:
            parsed_external_url = urlparse(external_url)
            if parsed_external_url.scheme not in {"http", "https"} or not parsed_external_url.netloc:
                external_url = ""
        attention_acknowledged_present = (
            "attention_acknowledged" in item or "attentionAcknowledged" in item
        )
        attention_acknowledged = parse_inventory_bool(
            item.get("attention_acknowledged", item.get("attentionAcknowledged", False))
        )
        is_gateway = parse_inventory_bool(item.get("is_gateway", item.get("isGateway", False)))
        role = import_inventory_role(item)
        room = import_inventory_room(item)
        first_seen = parse_inventory_datetime(
            item.get("first_seen") or item.get("firstSeen"),
            now,
        )
        last_seen = parse_inventory_datetime(
            item.get("last_seen") or item.get("lastSeen"),
            first_seen,
        )
        raw_status = str(item.get("status") or "").strip().lower()
        device_status = (
            raw_status if raw_status in Device.Status.values else Device.Status.OFFLINE
        )

        duplicate_devices = Device.objects.filter(ip=ip).exclude(mac=mac)
        for duplicate in duplicate_devices:
            if should_remove_import_ip_duplicate(duplicate):
                duplicate.delete()
                removed_duplicates += 1

        defaults = {
            "name": name,
            "ip": ip,
            "vendor": imported_vendor,
            "vendor_source": vendor_source,
            "icon": import_inventory_icon(item.get("icon") or item.get("iconName")),
            "secondary_icon": import_inventory_icon(
                item.get("secondary_icon") or item.get("secondaryIcon") or item.get("secondaryIconName"),
                "",
            ),
            "hostname": hostname,
            "hostname_source": hostname_source,
            "known": parse_inventory_bool(item.get("known", item.get("isKnown", False))),
            "is_gateway": is_gateway,
            "online": device_status != Device.Status.OFFLINE,
            "status": device_status,
            "lastseen": last_seen,
        }
        if role is not None:
            defaults["role"] = role or ("gateway" if is_gateway else "device")
        if room is not None:
            defaults["room"] = room
        if comments_present:
            defaults["comments"] = comments
        if external_url_present:
            defaults["external_url"] = external_url[:2048]

        device, was_created = Device.objects.get_or_create(
            mac=mac,
            defaults={
                **defaults,
                "role": role or ("gateway" if is_gateway else "device"),
                "room": room or "",
                "firstseen": first_seen,
            },
        )
        if not was_created:
            for field, value in defaults.items():
                setattr(device, field, value)
            if first_seen < device.firstseen:
                device.firstseen = first_seen
            device.save(
                update_fields=[
                    "name",
                    "ip",
                    "vendor",
                    "vendor_source",
                    "icon",
                    "secondary_icon",
                    "hostname",
                    "hostname_source",
                    *(['role'] if role is not None else []),
                    *(['room'] if room is not None else []),
                    *(["comments"] if comments_present else []),
                    *(["external_url"] if external_url_present else []),
                    "known",
                    "is_gateway",
                    "online",
                    "status",
                    "firstseen",
                    "lastseen",
                ]
            )
        created += 1 if was_created else 0
        updated += 0 if was_created else 1

        for port in normalize_inventory_ports(item.get("open_ports") or item.get("openPorts")):
            DevicePort.objects.update_or_create(
                device=device,
                port=port,
                protocol="tcp",
                defaults={
                    "open": True,
                    "lastseen": last_seen,
                },
            )

        if attention_acknowledged_present:
            device.attention_acknowledged_signature = (
                device_risk_signature(device)
                if attention_acknowledged and device.known
                else ""
            )
            device.save(update_fields=["attention_acknowledged_signature"])

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "removed_duplicates": removed_duplicates,
        "total": len(imported_devices),
    }


def inventory_export_response():
    devices = Device.objects.prefetch_related("ports").order_by("name", "ip")
    return JsonResponse(
        {
            "format": INVENTORY_FORMAT,
            "version": 1,
            "exported_at": utc_isoformat(timezone.now()),
            "devices": [inventory_device_payload(device) for device in devices],
            "notification": {
                "title": "Inventory exported",
                "message": "The device inventory file is ready.",
            },
        }
    )


def inventory_import_response(payload, source="LanGuard"):
    try:
        result = import_inventory_devices(payload)
    except ValidationError:
        raise
    except (IntegrityError, DatabaseError):
        LOGGER.exception("Inventory import failed because of a database error")
        return Response(
            {
                "status": "ERROR",
                "detail": "Inventory import failed because the database schema is out of date or the data is invalid. Run migrations and try again.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception:
        LOGGER.exception("Inventory import failed")
        return Response(
            {
                "status": "ERROR",
                "detail": "Inventory import failed. Check the backend logs for details.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(
        {
            "status": "OK",
            "info": (
                f"Imported {result['created']} new devices from {source} and updated "
                f"{result['updated']} existing devices."
            ),
            "data": result,
            "notification": {
                "title": "Inventory imported",
                "message": (
                    f"Created {result['created']}, updated {result['updated']}, "
                    f"and skipped {result['skipped']} devices."
                ),
            },
        },
        status=status.HTTP_200_OK,
    )


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

    serializer = AppSettingsSerializer(config, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return success_response(
        AppSettingsSerializer(config).data,
        "Settings saved",
        "Scanner, notification, and integration settings were updated.",
    )


@extend_schema(request=AdGuardConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_adguard(request):
    serializer = AdGuardConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    config = AppSettings.load()
    password = data.get("password") or config.adguard_password
    try:
        result = test_adguard_connection(
            data["url"],
            data.get("username", "").strip(),
            password,
        )
    except AdGuardError as exc:
        return error_response(
            "AdGuard Home connection failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    query_log = "enabled" if result.get("query_log_enabled") else "disabled"
    return success_response(
        result,
        "AdGuard Home connected",
        f"Connection succeeded. Query log is {query_log}.",
    )


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_adguard(request):
    try:
        result = sync_adguard_query_log()
    except AdGuardError as exc:
        return error_response(
            "AdGuard Home sync failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    return success_response(
        result,
        "AdGuard Home synced",
        (
            f"Matched {result.get('matched', 0)} queries across "
            f"{result.get('domains_updated', 0)} device domains."
        ),
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def device_dns_activity(request):
    id_ = request.query_params.get("id")
    if not id_:
        raise ValidationError({"id": "Device id is required."})

    target = get_object_or_404(Device, pk=id_)
    base_queryset = DeviceDNSActivity.objects.filter(device=target)
    queryset = base_queryset
    search = str(request.query_params.get("search") or "").strip()
    blocked = parse_bool_param(request.query_params, "blocked")
    ordering = request.query_params.get("ordering", "-last_seen")
    allowed_ordering = {
        "domain",
        "-domain",
        "query_count",
        "-query_count",
        "blocked_count",
        "-blocked_count",
        "last_seen",
        "-last_seen",
    }
    if ordering not in allowed_ordering:
        raise ValidationError({"ordering": "Invalid DNS activity ordering."})
    if search:
        queryset = queryset.filter(domain__icontains=search)
    if blocked is True:
        queryset = queryset.filter(blocked_count__gt=0)
    elif blocked is False:
        queryset = queryset.filter(blocked_count=0)
    queryset = queryset.order_by(ordering, "domain", "query_type")

    totals = base_queryset.aggregate(
        total_queries=Sum("query_count"),
        blocked_queries=Sum("blocked_count"),
    )
    payload = paginated_payload(
        request,
        queryset,
        DeviceDNSActivitySerializer,
        default_limit=100,
        max_limit=500,
    )
    config = AppSettings.load()
    return Response(
        {
            **payload,
            "summary": {
                "unique_domains": base_queryset.values("domain").distinct().count(),
                "total_queries": totals["total_queries"] or 0,
                "blocked_queries": totals["blocked_queries"] or 0,
                "last_activity_at": utc_isoformat(
                    base_queryset.order_by("-last_seen")
                    .values_list("last_seen", flat=True)
                    .first()
                ),
            },
            "integration": {
                "enabled": config.adguard_enabled,
                "configured": bool(
                    config.adguard_url
                    and (not config.adguard_username or config.adguard_password)
                ),
                "last_sync_at": utc_isoformat(config.adguard_last_sync_at),
                "last_error": config.adguard_last_error,
            },
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dns_activity(request):
    base_queryset = DeviceDNSActivity.objects.select_related("device")
    queryset = base_queryset
    search = str(request.query_params.get("search") or "").strip()
    blocked = parse_bool_param(request.query_params, "blocked")
    ordering = request.query_params.get("ordering", "-last_seen")
    allowed_ordering = {
        "domain",
        "-domain",
        "query_count",
        "-query_count",
        "blocked_count",
        "-blocked_count",
        "last_seen",
        "-last_seen",
        "device__name",
        "-device__name",
    }
    if ordering not in allowed_ordering:
        raise ValidationError({"ordering": "Invalid DNS activity ordering."})
    if search:
        queryset = queryset.filter(
            Q(domain__icontains=search)
            | Q(device__name__icontains=search)
            | Q(device__ip__icontains=search)
            | Q(device__mac__icontains=search)
        )
    if blocked is True:
        queryset = queryset.filter(blocked_count__gt=0)
    elif blocked is False:
        queryset = queryset.filter(blocked_count=0)
    queryset = queryset.order_by(ordering, "domain", "query_type")

    totals = base_queryset.aggregate(
        total_queries=Sum("query_count"),
        blocked_queries=Sum("blocked_count"),
    )
    payload = paginated_payload(
        request,
        queryset,
        GlobalDNSActivitySerializer,
        default_limit=100,
        max_limit=500,
    )
    config = AppSettings.load()
    return Response(
        {
            **payload,
            "summary": {
                "unique_domains": base_queryset.values("domain").distinct().count(),
                "total_queries": totals["total_queries"] or 0,
                "blocked_queries": totals["blocked_queries"] or 0,
                "active_devices": base_queryset.values("device_id").distinct().count(),
                "last_activity_at": utc_isoformat(
                    base_queryset.order_by("-last_seen")
                    .values_list("last_seen", flat=True)
                    .first()
                ),
            },
            "integration": {
                "enabled": config.adguard_enabled,
                "configured": bool(
                    config.adguard_url
                    and (not config.adguard_username or config.adguard_password)
                ),
                "last_sync_at": utc_isoformat(config.adguard_last_sync_at),
                "last_error": config.adguard_last_error,
            },
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dns_unmatched_clients(request):
    base_queryset = AdGuardUnmatchedClient.objects.all()
    queryset = base_queryset
    search = str(request.query_params.get("search") or "").strip()
    ordering = request.query_params.get("ordering", "-last_seen")
    allowed_ordering = {
        "client",
        "-client",
        "query_count",
        "-query_count",
        "blocked_count",
        "-blocked_count",
        "last_seen",
        "-last_seen",
    }
    if ordering not in allowed_ordering:
        raise ValidationError({"ordering": "Invalid unmatched client ordering."})
    if search:
        queryset = queryset.filter(
            Q(client__icontains=search) | Q(last_domain__icontains=search)
        )
    queryset = queryset.order_by(ordering, "client")
    totals = base_queryset.aggregate(
        total_queries=Sum("query_count"),
        blocked_queries=Sum("blocked_count"),
    )
    payload = paginated_payload(
        request,
        queryset,
        AdGuardUnmatchedClientSerializer,
        default_limit=100,
        max_limit=500,
    )
    return Response(
        {
            **payload,
            "summary": {
                "clients": base_queryset.count(),
                "total_queries": totals["total_queries"] or 0,
                "blocked_queries": totals["blocked_queries"] or 0,
                "last_activity_at": utc_isoformat(
                    base_queryset.order_by("-last_seen")
                    .values_list("last_seen", flat=True)
                    .first()
                ),
            },
        },
        status=status.HTTP_200_OK,
    )
@extend_schema(
    request=NotificationTestSerializer,
    responses=inline_serializer(
        name="NotificationTestResponse",
        fields={
            "data": inline_serializer(
                name="NotificationTestResponseData",
                fields={
                    "channel": serializers.CharField(),
                    "message": serializers.CharField(),
                },
            )
        },
    ),
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_notification_channel(request):
    serializer = NotificationTestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    channel = data["channel"]

    try:
        if channel == NotificationDelivery.Channel.DISCORD:
            send_discord_test(data["discord_webhook"].strip())
        else:
            send_telegram_test(
                data["telegram_token"].strip(),
                data["telegram_user_id"].strip(),
            )
    except requests.Timeout:
        return error_response(
            "Test notification failed",
            f"{channel.title()} did not respond before the timeout.",
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    except requests.RequestException as exc:
        response_status = getattr(getattr(exc, "response", None), "status_code", None)
        LOGGER.warning(
            "Notification channel test failed: channel=%s status=%s",
            channel,
            response_status or "unavailable",
        )
        if channel == NotificationDelivery.Channel.TELEGRAM:
            if response_status == 400:
                detail = (
                    "Telegram rejected the chat. Check the chat ID and send /start "
                    "to the bot before testing. HTTP 400."
                )
            elif response_status == 401:
                detail = "Telegram rejected the bot token. HTTP 401."
            elif response_status == 403:
                detail = (
                    "Telegram cannot send to this chat. Check whether the bot is "
                    "blocked or lacks permission. HTTP 403."
                )
            elif response_status == 429:
                detail = "Telegram rate-limited the test notification. Try again later."
            elif response_status:
                detail = f"Telegram rejected the test notification. HTTP {response_status}."
            else:
                detail = "LanGuard could not connect to Telegram."
        else:
            detail = f"{channel.title()} rejected the test notification."
            if response_status:
                detail = f"{detail} HTTP {response_status}."
            else:
                detail = f"LanGuard could not connect to {channel.title()}."
        return error_response(
            "Test notification failed",
            detail,
            response_status=status.HTTP_502_BAD_GATEWAY,
        )

    message = f"Test notification sent to {channel.title()}."
    return success_response(
        {"channel": channel, "message": message},
        "Test notification sent",
        message,
    )


@extend_schema(
    methods=["GET"],
    responses=HomeMapLayoutSerializer,
)
@extend_schema(
    methods=["PUT"],
    request=HomeMapLayoutSerializer,
    responses=HomeMapLayoutSerializer,
)
@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAuthenticated])
def home_map_layout(request):
    config = AppSettings.load()

    if request.method == "GET":
        return Response({"data": {"layout": config.home_map_layout or {}}})

    serializer = HomeMapLayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config.home_map_layout = serializer.validated_data["layout"]
    config.save(update_fields=["home_map_layout", "updated_at"])
    return success_response(
        {"layout": config.home_map_layout or {}},
        "Layout saved",
        "Home map layout was updated.",
    )


@extend_schema(
    request=inline_serializer(
        name="MaintenanceCleanupRequest",
        fields={
            "target": serializers.ChoiceField(
                choices=["events", "scan_runs", "notifications", "dns_activity"]
            ),
            "older_than_days": serializers.IntegerField(min_value=1, max_value=3650, required=False),
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
            raise ValidationError({"older_than_days": "Must be between 1 and 3650 days."})

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


@extend_schema(
    responses=inline_serializer(
        name="SetupStatusResponse",
        fields={"registration_open": serializers.BooleanField()},
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def setup_status(request):
    return Response(
        {"registration_open": not User.objects.exists()},
        status=status.HTTP_200_OK,
    )


@permission_classes([AllowAny])
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        if User.objects.exists():
            return Response(
                {"error": "Registration is only available before the first user exists."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Call the serializer to validate and create the user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        LOGGER.info(f"New user created - {user.username}")
        # Generate a token for the newly created user
        token, created = Token.objects.get_or_create(user=user)

        # Return the username and token in the response
        return Response(
            auth_payload(user, token, account_created=True),
            status=status.HTTP_201_CREATED,
        )


@permission_classes([AllowAny])
class UserLoginView(APIView):
    @extend_schema(
        request=inline_serializer(
            name="UserLoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(write_only=True),
            },
        ),
        responses=inline_serializer(
            name="AuthTokenResponse",
            fields={
                "username": serializers.CharField(),
                "token": serializers.CharField(),
            },
        ),
    )
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            token, created = Token.objects.get_or_create(user=user)
            return Response(auth_payload(user, token), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )


@permission_classes([permissions.IsAuthenticated])
class UserEditView(generics.UpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        # Get the current authenticated user
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class UserLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses=inline_serializer(
            name="MessageResponse",
            fields={"message": serializers.CharField()},
        ),
    )
    def post(self, request, *args, **kwargs):
        logout(request)
        return Response({"message": "User logged out"}, status=status.HTTP_200_OK)


@extend_schema(
    methods=["GET"],
    responses=UserManagementSerializer(many=True),
)
@extend_schema(
    methods=["POST"],
    request=UserManagementSerializer,
    responses=UserManagementSerializer,
)
@extend_schema(
    methods=["PUT"],
    request=UserManagementSerializer,
    responses=UserManagementSerializer,
)
@extend_schema(
    methods=["DELETE"],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def users(request):
    is_staff = request.user.is_staff

    if request.method == "GET":
        queryset = User.objects.order_by("username") if is_staff else User.objects.filter(pk=request.user.pk)
        serializer = UserManagementSerializer(
            queryset,
            many=True,
        )
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    if request.method == "POST":
        if not is_staff:
            return Response(
                {"detail": "You do not have permission to create users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = UserManagementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        LOGGER.info("User created - %s", user.username)
        return success_response(
            UserManagementSerializer(user).data,
            "User created",
            f"{user.username} can now sign in.",
            response_status=status.HTTP_201_CREATED,
        )

    id_ = parse_int_param(request.query_params, "id", default=0, minimum=1)
    user = get_object_or_404(User, pk=id_)
    if not is_staff and user.pk != request.user.pk:
        return Response(
            {"detail": "You do not have permission to edit this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PUT":
        data = request.data.copy()
        if not is_staff:
            data.pop("is_staff", None)
            data.pop("is_superuser", None)
            data.pop("is_active", None)
        serializer = UserManagementSerializer(user, data=request.data, partial=True)
        if not is_staff:
            serializer = UserManagementSerializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        next_is_staff = serializer.validated_data.get("is_staff", user.is_staff)
        next_is_active = serializer.validated_data.get("is_active", user.is_active)
        if user.is_staff and user.is_active and not (next_is_staff and next_is_active):
            if active_staff_count() <= 1:
                return Response(
                    {"error": "Cannot remove the last active admin user."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        user = serializer.save()
        LOGGER.info("User updated - %s", user.username)
        return success_response(
            UserManagementSerializer(user).data,
            "User saved",
            f"{user.username} was updated.",
        )

    if not is_staff:
        return Response(
            {"detail": "You do not have permission to delete users."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if User.objects.count() <= 1:
        return Response(
            {"error": "Cannot delete the last user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.is_staff and staff_count() <= 1:
        return Response(
            {"error": "Cannot delete the last admin user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.is_staff and user.is_active and active_staff_count() <= 1:
        return Response(
            {"error": "Cannot delete the last active admin user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    username = user.username
    user.delete()
    LOGGER.info("User deleted - %s", username)
    return success_response(
        {},
        "User deleted",
        f"{username} was removed.",
        status="OK",
    )


# Endpoint for managing devices (GET, PUT, DELETE)
@extend_schema(
    methods=["GET"],
    responses=OpenApiTypes.OBJECT,
)
@extend_schema(
    methods=["PUT"],
    request=DeviceSerializer,
    responses=OpenApiTypes.OBJECT,
)
@extend_schema(
    methods=["DELETE"],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def device(request):
    all_devices = Device.objects.all().count()
    online_devices = Device.objects.exclude(status=Device.Status.OFFLINE).count()
    offline_devices = Device.objects.filter(status=Device.Status.OFFLINE).count()
    new_devices = Device.objects.filter(known=False).count()
    open_ports = DevicePort.objects.filter(open=True).count()
    counters = {
        "all_devices": all_devices,
        "online_devices": online_devices,
        "offline_devices": offline_devices,
        "new_devices": new_devices,
        "open_ports": open_ports,
    }

    # Handle GET request to retrieve devices
    if request.method == "GET":
        id_ = request.query_params.get("id", None)
        if not id_:
            devices = Device.objects.prefetch_related("ports").all()
            online = parse_bool_param(request.query_params, "online")
            device_status = request.query_params.get("status")
            known = parse_bool_param(request.query_params, "known")
            search = request.query_params.get("search")
            open_port = request.query_params.get("open_port")
            first_seen = request.query_params.get("first_seen")

            if device_status:
                if device_status not in Device.Status.values:
                    raise ValidationError({"status": "Invalid device status."})
                devices = devices.filter(status=device_status)
            elif online is not None:
                devices = devices.filter(online=online)
            if known is not None:
                devices = devices.filter(known=known)
            if search:
                devices = devices.filter(
                    Q(name__icontains=search)
                    | Q(ip__icontains=search)
                    | Q(mac__icontains=search)
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

            payload = paginated_device_payload(request, devices)
            return Response(
                {
                    "data": payload["data"],
                    "counters": counters,
                    "pagination": payload["pagination"],
                },
                status=status.HTTP_200_OK,
            )
        else:
            device = get_object_or_404(Device, pk=id_)
            serializer = DeviceSerializer(device)
            return Response(
                {
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

    # Handle PUT request to update device
    if request.method == "PUT":
        id_ = request.query_params.get("id", None)
        if not id_:
            return Response(
                {
                    "status": "Error",
                    "info": "Id is missing",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = get_object_or_404(Device, pk=id_)
        serializer = DeviceSerializer(device, data=request.data, partial=True)
        if serializer.is_valid():
            device = serializer.save()
            LOGGER.info(
                f"Device ({device.id}) updated - Name: {device.name} / Icon: {device.icon} / Known: {device.known}"
            )
            return success_response(
                {"id": device.id},
                "Device saved",
                f"{device.name} was updated.",
                response_status=status.HTTP_202_ACCEPTED,
                status="OK",
            )
        else:
            return Response(
                {
                    "status": "Error",
                    "info": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Handle DELETE request to delete device
    if request.method == "DELETE":
        id_ = request.query_params.get("id", None)
        if not id_:
            return Response(
                {
                    "status": "Error",
                    "info": "Id is missing",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = get_object_or_404(Device, pk=id_)
        LOGGER.warning(
            f"Device ({device.id}) {device.name} - deleted successfully",
        )
        device.delete()
        return success_response(
            {"id": id_},
            "Device deleted",
            "The device was removed.",
            response_status=status.HTTP_202_ACCEPTED,
            status="OK",
        )


@extend_schema(
    request=inline_serializer(
        name="ScanNowRequest",
        fields={
            "ip_range": serializers.CharField(required=False),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def scan_now(request):
    ip_range = request.data.get("ip_range") or AppSettings.load().ip_range
    try:
        ip_range = validate_ip_range(ip_range)
    except ValueError as exc:
        raise ValidationError({"ip_range": str(exc)}) from exc

    try:
        scan_run = scan(ip_range)
    except Exception as exc:
        LOGGER.exception("Scan failed for %s", ip_range)
        failed_scan = ScanRun.objects.filter(ip_range=ip_range).first()
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
        "LanGuard finished scanning the configured network range.",
        response_status=status.HTTP_202_ACCEPTED,
        status="OK",
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def export_diagnostics(request):
    generated_at = timezone.now()
    filename = f"languard-diagnostics-{generated_at.strftime('%Y%m%d-%H%M%S')}.json"
    return success_response(
        {
            "filename": filename,
            "report": build_diagnostics_report(),
        },
        "Diagnostics ready",
        "A sanitized diagnostics report was generated.",
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


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def scan_status(request):
    latest_scan = ScanRun.objects.exclude(status=ScanRun.Status.RUNNING).first()
    active_scan = ScanRun.objects.filter(status=ScanRun.Status.RUNNING).first()
    active_scan = reconcile_scan_status(latest_scan, active_scan)
    visible_scan = active_scan or latest_scan
    app_config = AppSettings.load()
    now = timezone.now()
    duration_seconds = None
    if visible_scan:
        finished_at = visible_scan.finished_at or now
        duration_seconds = max(0, int((finished_at - visible_scan.started_at).total_seconds()))
    return Response(
        {
            "data": ScanRunSerializer(latest_scan).data if latest_scan else None,
            "active_scan": ScanRunSerializer(active_scan).data if active_scan else None,
            "visibility": {
                "is_scanning": active_scan is not None,
                "current_range": visible_scan.ip_range if visible_scan else "",
                "started_at": utc_isoformat(visible_scan.started_at) if visible_scan else None,
                "finished_at": utc_isoformat(visible_scan.finished_at) if visible_scan else None,
                "duration_seconds": duration_seconds,
                "last_error": visible_scan.error if visible_scan and visible_scan.error else "",
            },
            "time_zone": app_config.time_zone,
            "counters": {
                "all_devices": Device.objects.count(),
                "online_devices": Device.objects.exclude(status=Device.Status.OFFLINE).count(),
                "offline_devices": Device.objects.filter(status=Device.Status.OFFLINE).count(),
                "open_ports": DevicePort.objects.filter(open=True).count(),
                "unnotified_events": NetworkEvent.objects.filter(notified=False).count(),
            },
        },
        status=status.HTTP_200_OK,
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


@extend_schema(responses=NotificationDeliverySerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def notifications(request):
    channel = request.query_params.get("channel")
    delivery_status = request.query_params.get("status")
    event_id = request.query_params.get("event")
    created_after = parse_datetime_param(request.query_params, "created_after")
    created_before = parse_datetime_param(request.query_params, "created_before")

    queryset = NotificationDelivery.objects.select_related("event")
    if channel:
        if channel not in NotificationDelivery.Channel.values:
            raise ValidationError({"channel": "Invalid notification channel."})
        queryset = queryset.filter(channel=channel)
    if delivery_status:
        if delivery_status not in NotificationDelivery.Status.values:
            raise ValidationError({"status": "Invalid notification status."})
        queryset = queryset.filter(status=delivery_status)
    if event_id:
        queryset = queryset.filter(
            event_id=parse_int_param(request.query_params, "event", 0, 1)
        )
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)

    return paginated_response(
        request,
        queryset,
        NotificationDeliverySerializer,
        default_limit=50,
        max_limit=500,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def export_db(request):
    return inventory_export_response()


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def import_db(request):
    return inventory_import_response(request.data)


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def export_devices(request):
    return inventory_export_response()


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def import_devices(request):
    return inventory_import_response(request.data)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def import_watchyourlan_devices(request):
    payload = watchyourlan_devices_from_payload(request.data)
    return inventory_import_response(payload, source="WatchYourLAN")
    GlobalDNSActivitySerializer,
