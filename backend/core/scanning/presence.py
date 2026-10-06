import ipaddress
import logging

from django.conf import settings
from django.utils import timezone
import scapy.all as scapy

from ..models import Device, NetworkEvent
from .events import create_event
from .ports import normalize_scan_ports, scan_open_ports, sync_device_ports
from .ranges import validate_ip_ranges


LOGGER = logging.getLogger(__name__)


def mark_devices_outside_scan_ranges_offline(previous_ranges, current_ranges, now=None):
    previous_networks = [
        ipaddress.ip_network(network_range, strict=False)
        for network_range in validate_ip_ranges(previous_ranges)
    ]
    current_networks = [
        ipaddress.ip_network(network_range, strict=False)
        for network_range in validate_ip_ranges(current_ranges)
    ]
    if previous_networks == current_networks:
        return 0

    now = now or timezone.now()
    updated_devices = []
    for device in Device.objects.filter(online=True).iterator():
        try:
            address = ipaddress.ip_address(device.ip)
        except ValueError:
            continue
        if not any(address in network for network in previous_networks):
            continue
        if any(address in network for network in current_networks):
            continue

        device.online = False
        device.missed_scans = 0
        set_device_status(
            device,
            Device.Status.OFFLINE,
            Device.StatusSource.NONE,
            "Outside the configured network ranges.",
            now=now,
        )
        updated_devices.append(device)

    if updated_devices:
        Device.objects.bulk_update(
            updated_devices,
            [
                "online",
                "missed_scans",
                "status",
                "status_source",
                "status_reason",
                "last_status_check",
            ],
        )
    return len(updated_devices)

def clear_stale_gateways(gateway_ip):
    if not gateway_ip:
        return 0
    return Device.objects.filter(is_gateway=True).exclude(ip=gateway_ip).update(is_gateway=False)

def should_confirm_offline_with_ports():
    return settings.PORT_SCAN_ENABLED and settings.SCAN_CONFIRM_OFFLINE_WITH_PORTS

def should_confirm_offline_with_icmp():
    return settings.SCAN_CONFIRM_OFFLINE_WITH_ICMP

def status_reason(source, detail=""):
    labels = {
        Device.StatusSource.ARP: "Responded to ARP discovery",
        Device.StatusSource.LOCAL: "Detected on the local scanner interface",
        Device.StatusSource.PORT: "Responded on open ports",
        Device.StatusSource.ICMP: "Responded to ICMP ping",
        Device.StatusSource.RECENT: "Recently seen during scan grace period",
        Device.StatusSource.NONE: "No discovery signal responded",
    }
    reason = labels.get(source, "")
    if detail:
        return f"{reason}: {detail}" if reason else detail
    return reason

def set_device_status(device, status_value, source, reason="", now=None):
    now = now or timezone.now()
    device.status = status_value
    device.status_source = source
    device.status_reason = reason or status_reason(source)
    device.last_status_check = now

def is_mobile_device(device):
    return device.icon in {"phone", "tablet", "smart-watch"}

def is_sleeping_device(device):
    return device.icon in {
        "blinds",
        "ceiling-light",
        "desk-lamp",
        "led-strip",
        "light",
        "shutter",
        "temperature-humidity-sensor",
        "thermostat",
    }

def offline_miss_limit(device):
    if is_mobile_device(device):
        return settings.SCAN_MOBILE_OFFLINE_AFTER_MISSES
    if is_sleeping_device(device):
        return settings.SCAN_SLEEPING_OFFLINE_AFTER_MISSES
    return settings.SCAN_OFFLINE_AFTER_MISSES

def offline_confirmation_ports(device):
    configured_ports = normalize_scan_ports()
    known_open_ports = list(
        device.ports.filter(open=True)
        .order_by("port")
        .values_list("port", flat=True)
    )
    confirmation_ports = []

    for port in configured_ports + known_open_ports:
        if port in confirmation_ports:
            continue
        if len(confirmation_ports) >= settings.PORT_SCAN_MAX_PORTS:
            break
        confirmation_ports.append(port)

    return confirmation_ports

def icmp_responds(ip):
    if not should_confirm_offline_with_icmp():
        return False

    try:
        packet = scapy.IP(dst=ip) / scapy.ICMP()
        return scapy.sr1(packet, timeout=settings.SCAN_ICMP_TIMEOUT, verbose=False) is not None
    except Exception as exc:
        LOGGER.debug("ICMP confirmation failed for %s: %s", ip, exc)
        return False

def keep_online_if_ports_respond(device, scan_run=None, now=None):
    if not should_confirm_offline_with_ports():
        return False

    now = now or timezone.now()
    try:
        open_ports = scan_open_ports(device.ip, ports=offline_confirmation_ports(device))
    except OSError as exc:
        LOGGER.debug("Port confirmation failed for %s: %s", device.ip, exc)
        return False

    device.last_port_scan = now
    if not open_ports:
        device.save(update_fields=["last_port_scan"])
        return False

    device.online = True
    device.missed_scans = 0
    device.lastseen = now
    port_list = ", ".join(f"tcp/{port['port']}" for port in open_ports)
    set_device_status(
        device,
        Device.Status.ONLINE,
        Device.StatusSource.PORT,
        status_reason(Device.StatusSource.PORT, port_list),
        now=now,
    )
    device.save(
        update_fields=[
            "online",
            "missed_scans",
            "lastseen",
            "last_port_scan",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
    )
    sync_device_ports(device, open_ports, scan_run=scan_run)
    return True

def keep_online_if_icmp_responds(device, now=None):
    now = now or timezone.now()
    if not icmp_responds(device.ip):
        return False

    device.online = True
    device.missed_scans = 0
    device.lastseen = now
    set_device_status(
        device,
        Device.Status.ONLINE,
        Device.StatusSource.ICMP,
        now=now,
    )
    device.save(
        update_fields=[
            "online",
            "missed_scans",
            "lastseen",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
    )
    return True

def mark_missing_devices_offline(online_macs, scan_run=None, ip_ranges=None):
    offline_devices = Device.objects.exclude(mac__in=online_macs).filter(online=True, archived=False)
    networks = [
        ipaddress.ip_network(network_range, strict=False)
        for network_range in validate_ip_ranges(ip_ranges)
    ] if ip_ranges else []
    for device in offline_devices:
        if networks:
            try:
                if not any(ipaddress.ip_address(device.ip) in network for network in networks):
                    continue
            except ValueError:
                continue
        now = timezone.now()
        device.missed_scans += 1
        miss_limit = offline_miss_limit(device)
        if device.missed_scans < miss_limit:
            status_value = (
                Device.Status.SLEEPING
                if is_sleeping_device(device)
                else Device.Status.RECENTLY_SEEN
            )
            set_device_status(
                device,
                status_value,
                Device.StatusSource.RECENT,
                f"Missed {device.missed_scans}/{miss_limit} scans; keeping device in grace period.",
                now=now,
            )
            device.save(
                update_fields=[
                    "missed_scans",
                    "status",
                    "status_source",
                    "status_reason",
                    "last_status_check",
                ]
            )
            continue

        if keep_online_if_ports_respond(device, scan_run=scan_run, now=now):
            continue

        if keep_online_if_icmp_responds(device, now=now):
            continue

        device.online = False
        set_device_status(
            device,
            Device.Status.OFFLINE,
            Device.StatusSource.NONE,
            f"No discovery signal after {device.missed_scans} missed scans.",
            now=now,
        )
        device.save(
            update_fields=[
                "online",
                "missed_scans",
                "status",
                "status_source",
                "status_reason",
                "last_status_check",
            ]
        )
        create_event(
            NetworkEvent.EventType.DEVICE_OFFLINE,
            device=device,
            scan_run=scan_run,
            message=f"{device.name} went offline",
        )
