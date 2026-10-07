import logging
from datetime import timedelta

from django.utils import timezone
from scapy.data import ManufDA

from ..models import Device, NetworkEvent
from .discovery import get_hostname
from .events import create_event
from .identity import (
    guess_device_icon,
    guess_device_identity,
    guess_device_name,
    is_default_device_name,
    mismatched_default_haa_hostname,
    preferred_vendor,
    validated_hostname,
)
from .ports import scan_open_ports, should_scan_ports, sync_device_ports
from .presence import set_device_status
from .vendor import manuf_vendor


LOGGER = logging.getLogger(__name__)
IP_IDENTITY_CONFLICT_WINDOW = timedelta(hours=1)
IP_IDENTITY_CONFLICT_MARKER = " was reported by multiple MAC addresses: "


def sync_discovered_device(
    element,
    oui=None,
    scan_run=None,
    scan_started_at=None,
    gateway_ip="",
    hostname_hints=None,
    vendor_hints=None,
    snmp_hints=None,
    status_source=Device.StatusSource.ARP,
):
    scan_started_at = scan_started_at or timezone.now()
    ip = element[1].psrc
    mac = element[1].hwsrc.lower()
    conflict_cutoff = scan_started_at - IP_IDENTITY_CONFLICT_WINDOW
    conflicting_devices = list(
        Device.objects.filter(ip=ip, archived=False)
        .exclude(mac=mac)
        .filter(lastseen__gte=conflict_cutoff)
    )
    conflict_reason = ""
    if conflicting_devices:
        conflict_macs = sorted({mac, *(device.mac for device in conflicting_devices)})
        displayed_macs = ", ".join(conflict_macs[:4])
        if len(conflict_macs) > 4:
            displayed_macs = f"{displayed_macs} (+{len(conflict_macs) - 4} more)"
        conflict_reason = (
            f"IP {ip} was reported by multiple MAC addresses: {displayed_macs}"
        )
        Device.objects.filter(pk__in=[device.pk for device in conflicting_devices]).update(
            identity_conflict_reason=conflict_reason,
            identity_conflict_detected_at=scan_started_at,
        )
    vendor = ManufDA.lookup(oui, mac) if oui else None
    manuf_name = manuf_vendor(mac)
    scapy_name = preferred_vendor(vendor[1] if vendor else "")
    vendor_hint = "" if conflict_reason else (vendor_hints or {}).get(ip, "")
    hinted_name = vendor_hint[0] if isinstance(vendor_hint, tuple) else vendor_hint
    hinted_source = vendor_hint[1] if isinstance(vendor_hint, tuple) else ""
    vendor_name = manuf_name or scapy_name or preferred_vendor(hinted_name)
    hostname_result = (
        ("", "")
        if conflict_reason
        else get_hostname(
            ip=ip,
            hostname_hints=hostname_hints,
            include_source=True,
            dns_server=gateway_ip,
        )
    )
    if isinstance(hostname_result, tuple):
        hostname, hostname_source = hostname_result
    else:
        hostname, hostname_source = hostname_result, ""
    hostname = validated_hostname(hostname, mac)
    if not hostname:
        hostname_source = ""
    vendor_source = (
        Device.IdentitySource.MANUF
        if manuf_name or scapy_name
        else hinted_source if vendor_name else ""
    )
    ports_opened = 0
    ports_closed = 0
    new_devices = 0
    is_gateway = bool(gateway_ip and ip == gateway_ip)

    try:
        device = Device.objects.get(mac=mac)
        was_online = device.online
        was_known = device.known
        previous_ip = device.ip
        resolved_conflict_reason = ""
        update_fields = [
            "archived",
            "ip",
            "online",
            "lastseen",
            "missed_scans",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
        if conflict_reason:
            device.identity_conflict_reason = conflict_reason
            device.identity_conflict_detected_at = scan_started_at
            update_fields.extend(["identity_conflict_reason", "identity_conflict_detected_at"])
        elif (
            device.identity_conflict_reason.startswith("IP ")
            and IP_IDENTITY_CONFLICT_MARKER in device.identity_conflict_reason
        ):
            resolved_conflict_reason = device.identity_conflict_reason
            device.identity_conflict_reason = ""
            device.identity_conflict_detected_at = None
            update_fields.extend(["identity_conflict_reason", "identity_conflict_detected_at"])
        device.ip = ip
        device.archived = False
        device.online = True
        device.lastseen = scan_started_at
        device.missed_scans = 0
        existing_hostname_is_invalid = mismatched_default_haa_hostname(device.hostname, mac)
        if not conflict_reason or existing_hostname_is_invalid:
            resolved_hostname = hostname[:255] if hostname else ""
            if device.hostname != resolved_hostname:
                device.hostname = resolved_hostname
                update_fields.append("hostname")
            resolved_hostname_source = hostname_source if resolved_hostname else ""
            if device.hostname_source != resolved_hostname_source:
                device.hostname_source = resolved_hostname_source
                update_fields.append("hostname_source")
        resolved_vendor = preferred_vendor(
            observed_vendor=vendor_name,
        )
        if resolved_vendor != device.vendor:
            device.vendor = resolved_vendor
            update_fields.append("vendor")
        resolved_vendor_source = vendor_source if resolved_vendor else ""
        if device.vendor_source != resolved_vendor_source:
            device.vendor_source = resolved_vendor_source
            update_fields.append("vendor_source")
        set_device_status(
            device,
            Device.Status.ONLINE,
            status_source,
            now=scan_started_at,
        )
        if is_default_device_name(device.name):
            device.name = guess_device_name(hostname, resolved_vendor, mac)
            update_fields.append("name")
        if not was_known:
            inferred_icon = guess_device_icon(
                hostname=hostname,
                vendor=resolved_vendor,
                open_ports=device.ports.filter(open=True).values_list("port", flat=True),
            )
            if device.icon != inferred_icon:
                device.icon = inferred_icon
                update_fields.append("icon")
        if is_gateway:
            device.is_gateway = True
            device.known = True
            if is_default_device_name(device.name):
                device.name = "Gateway"
            if not was_known:
                device.icon = "router"
                update_fields.append("icon")
            update_fields.extend(["is_gateway", "known", "name"])
        device.save(
            update_fields=update_fields,
            ip_observed_at=scan_started_at,
            close_competing_ip_assignments=not conflict_reason,
        )

        if resolved_conflict_reason:
            Device.objects.filter(
                identity_conflict_reason=resolved_conflict_reason,
            ).exclude(pk=device.pk).update(
                identity_conflict_reason="",
                identity_conflict_detected_at=None,
            )

        if previous_ip != ip:
            create_event(
                NetworkEvent.EventType.IP_CHANGED,
                device=device,
                scan_run=scan_run,
                message=f"{device.name} changed IP from {previous_ip} to {ip}",
                metadata={
                    "old_ip": previous_ip,
                    "new_ip": ip,
                },
            )

        if not was_online:
            create_event(
                NetworkEvent.EventType.DEVICE_ONLINE,
                device=device,
                scan_run=scan_run,
                message=f"{device.name} came online",
            )
    except Device.DoesNotExist:
        resolved_vendor = preferred_vendor(
            observed_vendor=vendor_name,
        )
        identity = guess_device_identity(hostname, resolved_vendor, mac)
        if is_gateway:
            identity = {
                "name": "Gateway" if is_default_device_name(identity["name"]) else identity["name"],
                "icon": "router",
            }
        device = Device(
            icon=identity["icon"],
            name=identity["name"],
            ip=ip,
            mac=mac,
            vendor=resolved_vendor,
            vendor_source=vendor_source if resolved_vendor else "",
            hostname=hostname[:255] if hostname else "",
            hostname_source=hostname_source if hostname else "",
            identity_conflict_reason=conflict_reason,
            identity_conflict_detected_at=scan_started_at if conflict_reason else None,
            role="gateway" if is_gateway else "device",
            known=is_gateway,
            is_gateway=is_gateway,
            lastseen=scan_started_at,
        )
        device.save(
            ip_observed_at=scan_started_at,
            close_competing_ip_assignments=not conflict_reason,
        )
        set_device_status(
            device,
            Device.Status.ONLINE,
            status_source,
            now=scan_started_at,
        )
        device.save(update_fields=["status", "status_source", "status_reason", "last_status_check"])
        new_devices = 1
        LOGGER.info(
            "Create new device - Mac address: %s / IP: %s / Vendor: %s",
            mac,
            ip,
            device.vendor,
        )
        create_event(
            NetworkEvent.EventType.NEW_DEVICE,
            device=device,
            scan_run=scan_run,
            message=f"Found new device {device.name} at {device.ip}",
            metadata={
                "ip": device.ip,
                "mac": device.mac,
                "vendor": device.vendor,
            },
        )

    if should_scan_ports(device, now=scan_started_at):
        open_ports = scan_open_ports(ip)
        if not device.known:
            inferred_icon = guess_device_icon(
                hostname=device.name,
                vendor=device.vendor,
                open_ports=open_ports,
            )
            if device.icon != inferred_icon:
                device.icon = inferred_icon
                device.save(update_fields=["icon"])
        port_stats = sync_device_ports(device, open_ports, scan_run=scan_run)
        ports_opened += port_stats["ports_opened"]
        ports_closed += port_stats["ports_closed"]
        device.last_port_scan = scan_started_at
        device.save(update_fields=["last_port_scan"])

    snmp_data = (snmp_hints or {}).get(ip)
    if snmp_data:
        update_fields = ["snmp_data", "snmp_last_seen"]
        device.snmp_data = snmp_data
        device.snmp_last_seen = scan_started_at
        inferred = {
            "access_point": ("accessPoint", "router"),
            "printer": ("printer", "printer"),
            "router": ("router", "router"),
            "switch": ("switch", "router"),
        }.get(snmp_data.get("device_type"))
        if inferred and not device.known:
            role, icon = inferred
            if device.role in {"", "device", "unknown"} and device.role != role:
                device.role = role
                update_fields.append("role")
            if device.icon in {"", "plus", "unknown"} and device.icon != icon:
                device.icon = icon
                update_fields.append("icon")
        device.save(update_fields=update_fields)

    return {
        "new_devices": new_devices,
        "ports_opened": ports_opened,
        "ports_closed": ports_closed,
    }
