import csv
import ipaddress
import io
import logging
from datetime import datetime, timezone as datetime_timezone
from urllib.parse import urlparse
from uuid import UUID

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..datetime_utils import utc_isoformat
from ..serializers import (
    device_attention_acknowledged,
    device_risk,
    device_risk_signature,
)
from ..models import Device, DevicePort

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
        "external_url_follow_device_ip": device.external_url_follow_device_ip,
        "homebox_item_id": str(device.homebox_item_id) if device.homebox_item_id else None,
        "archived": device.archived,
        "online_notification_preference": device.online_notification_preference,
        "offline_notification_preference": device.offline_notification_preference,
        "presence_expectation": device.presence_expectation,
        "offline_attention_after_days": device.offline_attention_after_days,
        "risk": risk_data["level"],
        "attention_acknowledged": device_attention_acknowledged(device, risk_data),
        "known": device.known,
        "is_visitor": device.is_visitor,
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


NETALERTX_MAX_CSV_BYTES = 5 * 1024 * 1024
NETALERTX_MAX_DEVICES = 10000
NETALERTX_ROLE_MAP = {
    "access point": "router",
    "ap": "router",
    "camera": "camera",
    "console": "gameConsole",
    "computer": "computer",
    "desktop": "computer",
    "firewall": "router",
    "gateway": "gateway",
    "hub": "hub",
    "hypervisor": "server",
    "intercom": "intercom",
    "game console": "gameConsole",
    "laptop": "laptop",
    "light": "light",
    "lock": "lock",
    "nas": "nas",
    "network attached storage": "nas",
    "phone": "phone",
    "printer": "printer",
    "router": "router",
    "sensor": "sensor",
    "server": "server",
    "smart plug": "smartPlug",
    "smart power strip": "smartPowerStrip",
    "smart relay": "smartRelay",
    "power meter": "powerMeter",
    "smartphone": "phone",
    "speaker": "speaker",
    "streamer": "streamer",
    "tablet": "tablet",
    "television": "tv",
    "tv": "tv",
    "watch": "watch",
    "workstation": "computer",
}


def netalertx_devices_from_csv(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("content"), str):
        raise ValidationError(
            {"detail": "Choose a devices.csv file exported from NetAlertX."}
        )

    content = payload["content"].lstrip("\ufeff")
    if not content.strip():
        raise ValidationError({"detail": "The selected NetAlertX CSV file is empty."})
    if len(content.encode("utf-8")) > NETALERTX_MAX_CSV_BYTES:
        raise ValidationError(
            {"detail": "The selected NetAlertX CSV file is larger than 5 MB."}
        )

    try:
        reader = csv.DictReader(io.StringIO(content, newline=""))
        fieldnames = {
            str(name or "").strip().lower() for name in reader.fieldnames or []
        }
        if "devmac" not in fieldnames or not ({"devlastip", "devip"} & fieldnames):
            raise ValidationError(
                {
                    "detail": (
                        "The selected file does not contain NetAlertX device export columns."
                    )
                }
            )
        rows = list(reader)
    except csv.Error as exc:
        raise ValidationError(
            {"detail": "The selected NetAlertX CSV file could not be parsed."}
        ) from exc

    if len(rows) > NETALERTX_MAX_DEVICES:
        raise ValidationError(
            {"detail": "The NetAlertX CSV file contains more than 10,000 devices."}
        )

    devices = []
    for source_row in rows:
        row = {
            str(key or "").strip().lower(): value
            for key, value in source_row.items()
            if key is not None
        }
        device_type = str(row.get("devtype") or "").strip()
        normalized_type = " ".join(
            device_type.lower().replace("_", " ").replace("-", " ").split()
        )
        role = NETALERTX_ROLE_MAP.get(normalized_type)
        hostname = str(row.get("devfqdn") or "").strip()
        if hostname.lower() in {"(unknown)", "(name not found)", "unknown"}:
            hostname = ""
        is_new = row.get("devisnew")

        device = {
            "name": row.get("devname") or hostname or "Device",
            "hostname": hostname,
            "hostname_source": Device.IdentitySource.IMPORTED if hostname else "",
            "ip": row.get("devlastip") or row.get("devip"),
            "mac": row.get("devmac"),
            "vendor": row.get("devvendor") or "",
            "vendor_source": (
                Device.IdentitySource.IMPORTED if row.get("devvendor") else ""
            ),
            "comments": row.get("devcomments") or "",
            "room": row.get("devlocation") or "",
            "known": (
                not parse_inventory_bool(is_new)
                if is_new not in (None, "")
                else False
            ),
            "status": (
                Device.Status.ONLINE
                if parse_inventory_bool(row.get("devpresentlastscan"))
                else Device.Status.OFFLINE
            ),
            "first_seen": row.get("devfirstconnection"),
            "last_seen": row.get("devlastconnection"),
        }
        if role:
            device["role"] = role
        if normalized_type == "gateway":
            device["is_gateway"] = True
        devices.append(device)

    return {
        "format": INVENTORY_FORMAT,
        "version": 1,
        "devices": devices,
    }


@transaction.atomic
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
        homebox_present = "homebox_item_id" in item
        homebox_item_id = None
        if homebox_present and item["homebox_item_id"]:
            try:
                homebox_item_id = UUID(str(item["homebox_item_id"]))
            except ValueError:
                homebox_present = False
        comments = str(item.get("comments") or "").strip()
        external_url_present = "external_url" in item or "externalUrl" in item
        external_url = str(item.get("external_url") or item.get("externalUrl") or "").strip()
        if external_url:
            parsed_external_url = urlparse(external_url)
            if (
                parsed_external_url.scheme not in {"http", "https"}
                or not parsed_external_url.netloc
                or not parsed_external_url.hostname
                or parsed_external_url.username is not None
                or parsed_external_url.password is not None
            ):
                external_url = ""
        external_url_follow_device_ip_present = (
            "external_url_follow_device_ip" in item
            or "externalUrlFollowDeviceIp" in item
        )
        external_url_follow_device_ip = parse_inventory_bool(
            item.get(
                "external_url_follow_device_ip",
                item.get("externalUrlFollowDeviceIp", False),
            )
        )
        if external_url_follow_device_ip:
            try:
                if ipaddress.ip_address(urlparse(external_url).hostname).version != 4:
                    external_url_follow_device_ip = False
            except (TypeError, ValueError):
                external_url_follow_device_ip = False
        valid_notification_preferences = set(Device.NotificationPreference.values)
        online_notification_preference_present = (
            "online_notification_preference" in item
            or "onlineNotificationPreference" in item
        )
        offline_notification_preference_present = (
            "offline_notification_preference" in item
            or "offlineNotificationPreference" in item
        )
        online_notification_preference = str(
            item.get(
                "online_notification_preference",
                item.get("onlineNotificationPreference", Device.NotificationPreference.INHERIT),
            )
        ).strip()
        offline_notification_preference = str(
            item.get(
                "offline_notification_preference",
                item.get("offlineNotificationPreference", Device.NotificationPreference.INHERIT),
            )
        ).strip()
        if online_notification_preference not in valid_notification_preferences:
            online_notification_preference = Device.NotificationPreference.INHERIT
        if offline_notification_preference not in valid_notification_preferences:
            offline_notification_preference = Device.NotificationPreference.INHERIT
        valid_presence_expectations = set(Device.PresenceExpectation.values)
        presence_expectation_present = (
            "presence_expectation" in item or "presenceExpectation" in item
        )
        presence_expectation = str(
            item.get(
                "presence_expectation",
                item.get("presenceExpectation", Device.PresenceExpectation.AUTOMATIC),
            )
        ).strip()
        if presence_expectation not in valid_presence_expectations:
            presence_expectation = Device.PresenceExpectation.AUTOMATIC
        offline_attention_after_days_present = (
            "offline_attention_after_days" in item
            or "offlineAttentionAfterDays" in item
        )
        raw_offline_attention_after_days = item.get(
            "offline_attention_after_days",
            item.get("offlineAttentionAfterDays"),
        )
        try:
            offline_attention_after_days = int(raw_offline_attention_after_days)
            if not 1 <= offline_attention_after_days <= 3650:
                offline_attention_after_days = None
        except (TypeError, ValueError):
            offline_attention_after_days = None
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

        duplicate_devices = Device.objects.filter(ip=ip, archived=False).exclude(mac=mac)
        retained_ip_duplicate = False
        for duplicate in duplicate_devices:
            if should_remove_import_ip_duplicate(duplicate):
                duplicate.delete()
                removed_duplicates += 1
            else:
                retained_ip_duplicate = True

        is_visitor_present = "is_visitor" in item or "isVisitor" in item
        is_visitor = parse_inventory_bool(
            item.get("is_visitor", item.get("isVisitor", False))
        )
        known = is_visitor or parse_inventory_bool(
            item.get("known", item.get("isKnown", False))
        )
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
            "known": known,
            "is_gateway": is_gateway,
            "online": device_status != Device.Status.OFFLINE,
            "status": device_status,
            "lastseen": last_seen,
        }
        if is_visitor_present or not known:
            defaults["is_visitor"] = is_visitor
        if online_notification_preference_present:
            defaults["online_notification_preference"] = online_notification_preference
        if offline_notification_preference_present:
            defaults["offline_notification_preference"] = offline_notification_preference
        if presence_expectation_present:
            defaults["presence_expectation"] = presence_expectation
        if offline_attention_after_days_present:
            defaults["offline_attention_after_days"] = (
                offline_attention_after_days
                if presence_expectation
                not in {
                    Device.PresenceExpectation.AUTOMATIC,
                    Device.PresenceExpectation.NEVER,
                }
                else None
            )
        if role is not None:
            defaults["role"] = role or ("gateway" if is_gateway else "device")
        if room is not None:
            defaults["room"] = room
        if comments_present:
            defaults["comments"] = comments
        if external_url_present:
            defaults["external_url"] = external_url[:2048]
        if external_url_follow_device_ip_present:
            defaults["external_url_follow_device_ip"] = external_url_follow_device_ip
        if homebox_present:
            defaults["homebox_item_id"] = homebox_item_id
        if isinstance(item.get("archived"), bool):
            defaults["archived"] = item["archived"]

        try:
            device = Device.objects.get(mac=mac)
            was_created = False
        except Device.DoesNotExist:
            device = Device(
                mac=mac,
                **{
                    **defaults,
                    "role": role or ("gateway" if is_gateway else "device"),
                    "room": room or "",
                    "firstseen": first_seen,
                },
            )
            device.save(
                ip_observed_at=now,
                close_competing_ip_assignments=not retained_ip_duplicate,
            )
            was_created = True
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
                    *(
                        ["external_url_follow_device_ip"]
                        if external_url_follow_device_ip_present
                        else []
                    ),
                    *(["homebox_item_id"] if homebox_present else []),
                    *(["archived"] if "archived" in defaults else []),
                    "known",
                    *(["is_visitor"] if "is_visitor" in defaults else []),
                    "is_gateway",
                    "online",
                    "status",
                    *(
                        ["online_notification_preference"]
                        if online_notification_preference_present
                        else []
                    ),
                    *(
                        ["offline_notification_preference"]
                        if offline_notification_preference_present
                        else []
                    ),
                    *(
                        ["presence_expectation"]
                        if presence_expectation_present
                        else []
                    ),
                    *(
                        ["offline_attention_after_days"]
                        if offline_attention_after_days_present
                        else []
                    ),
                    "firstseen",
                    "lastseen",
                ],
                ip_observed_at=now,
                close_competing_ip_assignments=not retained_ip_duplicate,
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


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def import_netalertx_devices(request):
    payload = netalertx_devices_from_csv(request.data)
    return inventory_import_response(payload, source="NetAlertX")
