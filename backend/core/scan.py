import logging
import ipaddress
import socket
import struct

from django.conf import settings
from django.utils import timezone
import scapy.all as scapy
from scapy.data import ManufDA

from .models import Device, DevicePort, NetworkEvent, ScanRun
from .notifications import notify_event


LOGGER = logging.getLogger(__name__)
DEFAULT_DEVICE_NAME = "Device"
DEFAULT_DEVICE_ICONS = {"", "plus", "unknown", "device", "desktop"}
DEVICE_GUESS_RULES = [
    {
        "icon": "smart-hub",
        "keywords": (
            "smart hub",
            "home hub",
            "aqara hub",
            "hub aqara",
            "aqara gateway",
            "gateway aqara",
            "aqura hub",
            "hub aqura",
            "aqura gateway",
            "gateway aqura",
        ),
    },
    {
        "icon": "router",
        "keywords": (
            "router",
            "gateway",
            "access point",
            "tp link",
            "tp-link",
            "tplink",
            "ubiquiti",
            "mikrotik",
            "deco",
        ),
    },
    {
        "icon": "phone",
        "keywords": ("iphone", "android", "phone", "mobile", "oneplus", "pixel", "galaxy"),
    },
    {
        "icon": "tablet",
        "keywords": ("ipad", "tablet", "tab "),
    },
    {
        "icon": "smart-watch",
        "keywords": ("watch", "smartwatch", "wearable"),
    },
    {
        "icon": "laptop",
        "keywords": ("macbook", "laptop", "notebook"),
    },
    {
        "icon": "streamer",
        "keywords": ("apple tv", "chromecast", "streamer", "streaming", "roku", "fire tv", "google cast"),
        "ports": (8008, 8009),
    },
    {
        "icon": "tv",
        "keywords": ("tv", "television"),
    },
    {
        "icon": "security-camera",
        "keywords": ("camera", "cam", "cctv", "hikvision", "dahua"),
        "ports": (554,),
    },
    {
        "icon": "shutter",
        "keywords": ("shutter", "roller shutter"),
    },
    {
        "icon": "blinds",
        "keywords": ("blind", "blinds", "shade", "curtain"),
    },
    {
        "icon": "led-strip",
        "keywords": ("led strip", "light strip", "strip light"),
    },
    {
        "icon": "desk-lamp",
        "keywords": ("desk lamp", "table lamp", "reading lamp"),
    },
    {
        "icon": "ceiling-light",
        "keywords": ("ceiling light", "downlight"),
    },
    {
        "icon": "light",
        "keywords": ("light", "bulb", "lamp"),
    },
    {
        "icon": "air-conditioner",
        "keywords": ("air conditioner", "air-conditioning", "aircon", "hvac"),
    },
    {
        "icon": "ceiling-fan",
        "keywords": ("ceiling fan",),
    },
    {
        "icon": "fan",
        "keywords": ("fan",),
    },
    {
        "icon": "thermostat",
        "keywords": ("thermostat", "heater"),
    },
    {
        "icon": "speaker",
        "keywords": ("speaker", "sonos", "homepod", "audio"),
    },
    {
        "icon": "printer",
        "keywords": ("printer", "canon", "brother", "epson", "hewlett", "hp"),
        "ports": (9100,),
    },
    {
        "icon": "server",
        "keywords": ("server", "nas", "casaos", "raspberry", "linux"),
        "ports": (22,),
    },
]
VENDOR_NAME_PROFILES = [
    {"keywords": ("hon hai", "foxconn"), "name": "Foxconn"},
    {"keywords": ("espresif", "espressif"), "name": "Espressif IoT device"},
    {"keywords": ("raspberry",), "name": "Raspberry Pi"},
    {"keywords": ("tp link", "tp-link", "tplink"), "name": "TP-Link"},
    {"keywords": ("ubiquiti",), "name": "Ubiquiti"},
    {"keywords": ("mikrotik",), "name": "MikroTik"},
    {"keywords": ("aqara", "aqura"), "name": "Aqara"},
    {"keywords": ("apple",), "name": "Apple"},
    {"keywords": ("google",), "name": "Google"},
    {"keywords": ("amazon",), "name": "Amazon"},
    {"keywords": ("samsung",), "name": "Samsung"},
    {"keywords": ("sony",), "name": "Sony"},
    {"keywords": ("lg electronics",), "name": "LG"},
    {"keywords": ("xiaomi",), "name": "Xiaomi"},
]


def get_hostname(ip):
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return clean_hostname(hostname)
    except (socket.herror, socket.gaierror, TimeoutError, OSError) as e:
        LOGGER.debug("Hostname lookup failed for %s: %s", ip, e)
        return ""


def clean_hostname(hostname):
    hostname = (hostname or "").strip().rstrip(".")
    if not hostname:
        return ""
    return hostname.split(".")[0].replace("-", " ").strip()


def short_vendor(vendor):
    vendor = (vendor or "").strip()
    suffixes = [
        " incorporated",
        " corporation",
        " equipment",
        " technologies",
        " technology",
        " co.,ltd.",
        " co., ltd.",
        " co ltd",
        " ltd.",
        " inc.",
        " llc",
    ]
    changed = True
    while changed:
        changed = False
        lowered = vendor.lower()
        for suffix in suffixes:
            if lowered.endswith(suffix):
                vendor = vendor[: -len(suffix)].strip(" ,.-") or vendor
                changed = True
                break
    return vendor


def guess_text(*values):
    return (
        " ".join(value or "" for value in values)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def open_port_numbers(open_ports=None):
    ports = set()
    for port in open_ports or []:
        if isinstance(port, dict):
            value = port.get("port")
        else:
            value = port
        try:
            ports.add(int(value))
        except (TypeError, ValueError):
            continue
    return ports


def vendor_profile_name(vendor):
    cleaned_vendor = short_vendor(vendor)
    text = guess_text(cleaned_vendor)
    for profile in VENDOR_NAME_PROFILES:
        if any(keyword in text for keyword in profile["keywords"]):
            return profile["name"]
    return cleaned_vendor


def is_default_device_name(name):
    cleaned = (name or "").strip().lower()
    return not cleaned or cleaned == DEFAULT_DEVICE_NAME.lower()


def is_default_device_icon(icon):
    return (icon or "").strip().lower() in DEFAULT_DEVICE_ICONS


def guess_device_rule(hostname="", vendor="", open_ports=None):
    text = guess_text(hostname, vendor_profile_name(vendor), vendor)
    ports = open_port_numbers(open_ports)
    for rule in DEVICE_GUESS_RULES:
        if any(keyword in text for keyword in rule.get("keywords", ())):
            return rule
        if ports and ports.intersection(rule.get("ports", ())):
            return rule
    return None


def guess_device_icon(hostname="", vendor="", open_ports=None):
    rule = guess_device_rule(hostname=hostname, vendor=vendor, open_ports=open_ports)
    return rule["icon"] if rule else "unknown"


def guess_device_name(hostname, vendor, mac):
    if hostname and not is_default_device_name(hostname):
        return hostname
    if vendor:
        return vendor_profile_name(vendor)
    return DEFAULT_DEVICE_NAME


def guess_device_identity(hostname="", vendor="", mac="", open_ports=None):
    return {
        "name": guess_device_name(hostname, vendor, mac),
        "icon": guess_device_icon(hostname=hostname, vendor=vendor, open_ports=open_ports),
    }


def get_service_name(port, protocol="tcp"):
    try:
        return socket.getservbyport(port, protocol)
    except OSError:
        return ""


def validate_ip_range(ip_range):
    try:
        network = ipaddress.ip_network(ip_range, strict=False)
    except ValueError as exc:
        raise ValueError("IP range must be a valid CIDR range or IP address.") from exc

    if network.version != 4:
        raise ValueError("Only IPv4 ranges are supported.")

    if network.num_addresses > settings.SCAN_MAX_HOSTS:
        raise ValueError(
            f"IP range is too large. Maximum allowed hosts: {settings.SCAN_MAX_HOSTS}."
        )

    is_allowed_private_range = (
        network.is_private or network.is_loopback or network.is_link_local
    )
    if not settings.SCAN_ALLOW_PUBLIC_RANGES and not is_allowed_private_range:
        raise ValueError("Public IP ranges are disabled.")

    return network.with_prefixlen


def default_gateway_from_proc_route(path="/proc/net/route"):
    try:
        with open(path, encoding="utf-8") as route_file:
            next(route_file, None)
            for line in route_file:
                fields = line.strip().split()
                if len(fields) < 3:
                    continue
                destination, gateway = fields[1], fields[2]
                if destination != "00000000" or gateway == "00000000":
                    continue
                return socket.inet_ntoa(struct.pack("<L", int(gateway, 16)))
    except (FileNotFoundError, OSError, ValueError):
        return ""
    return ""


def get_default_gateway_ip():
    return default_gateway_from_proc_route()


def clear_stale_gateways(gateway_ip):
    if not gateway_ip:
        return 0
    return Device.objects.filter(is_gateway=True).exclude(ip=gateway_ip).update(is_gateway=False)


def normalize_scan_ports(ports=None):
    ports = ports or settings.PORT_SCAN_PORTS
    normalized_ports = []

    for port in ports:
        try:
            normalized_port = int(port)
        except (TypeError, ValueError) as exc:
            raise ValueError("Port scan list must contain only integers.") from exc

        if normalized_port < 1 or normalized_port > 65535:
            raise ValueError("Port scan list must contain values from 1 to 65535.")
        if normalized_port not in normalized_ports:
            normalized_ports.append(normalized_port)

    if len(normalized_ports) > settings.PORT_SCAN_MAX_PORTS:
        raise ValueError(
            f"Too many ports configured. Maximum allowed ports: {settings.PORT_SCAN_MAX_PORTS}."
        )

    return normalized_ports


def scan_open_ports(ip, ports=None, timeout=None):
    ports = normalize_scan_ports(ports)
    timeout = timeout or settings.PORT_SCAN_TIMEOUT
    open_ports = []

    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, int(port)))
            if result == 0:
                open_ports.append(
                    {
                        "port": int(port),
                        "protocol": "tcp",
                        "service": get_service_name(int(port)),
                    }
                )

    return open_ports


def should_scan_ports(device, now=None):
    if not settings.PORT_SCAN_ENABLED:
        return False

    interval = settings.PORT_SCAN_INTERVAL
    if interval <= 0 or not device.last_port_scan:
        return True

    now = now or timezone.now()
    elapsed = now - device.last_port_scan
    return elapsed.total_seconds() >= interval * 60


def should_confirm_offline_with_ports():
    return settings.PORT_SCAN_ENABLED and settings.SCAN_CONFIRM_OFFLINE_WITH_PORTS


def should_confirm_offline_with_icmp():
    return settings.SCAN_CONFIRM_OFFLINE_WITH_ICMP


def status_reason(source, detail=""):
    labels = {
        Device.StatusSource.ARP: "Responded to ARP discovery",
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


def create_event(event_type, device, message, scan_run=None, device_port=None, metadata=None):
    metadata = metadata or {}
    event = NetworkEvent.objects.create(
        scan_run=scan_run,
        device=device,
        device_port=device_port,
        event_type=event_type,
        message=message,
        metadata=metadata,
    )
    if device.known:
        event.notified = True
        event.metadata = {
            **metadata,
            "notification_skipped": "known_device",
        }
        event.save(update_fields=["notified", "metadata"])
    else:
        notify_event(event)
    return event


def sync_device_ports(device, open_ports, scan_run=None):
    now = timezone.now()
    seen_ports = set()
    ports_opened = 0
    ports_closed = 0

    for port_data in open_ports:
        port = int(port_data["port"])
        protocol = port_data.get("protocol", "tcp")
        service = port_data.get("service", "")
        seen_ports.add((port, protocol))

        device_port, created = DevicePort.objects.get_or_create(
            device=device,
            port=port,
            protocol=protocol,
            defaults={
                "service": service,
                "open": True,
                "firstseen": now,
                "lastseen": now,
            },
        )
        was_open = device_port.open
        device_port.service = service
        device_port.open = True
        device_port.lastseen = now
        device_port.save(update_fields=["service", "open", "lastseen"])

        if created or not was_open:
            ports_opened += 1
            create_event(
                NetworkEvent.EventType.PORT_OPENED,
                device=device,
                device_port=device_port,
                scan_run=scan_run,
                message=f"{device.name} opened {protocol}/{port}",
                metadata={
                    "port": port,
                    "protocol": protocol,
                    "service": service,
                },
            )

    for device_port in device.ports.filter(open=True):
        key = (device_port.port, device_port.protocol)
        if key not in seen_ports:
            device_port.open = False
            device_port.lastseen = now
            device_port.save(update_fields=["open", "lastseen"])
            ports_closed += 1
            create_event(
                NetworkEvent.EventType.PORT_CLOSED,
                device=device,
                device_port=device_port,
                scan_run=scan_run,
                message=f"{device.name} closed {device_port.protocol}/{device_port.port}",
                metadata={
                    "port": device_port.port,
                    "protocol": device_port.protocol,
                    "service": device_port.service,
                },
            )

    return {
        "ports_opened": ports_opened,
        "ports_closed": ports_closed,
    }


def discover_devices(ip_range):
    ip_range = validate_ip_range(ip_range)
    discovered = {}

    for _ in range(max(1, settings.SCAN_ARP_RETRIES)):
        arp_request = scapy.ARP(pdst=ip_range)
        broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request
        answered = scapy.srp(
            arp_request_broadcast,
            timeout=settings.SCAN_ARP_TIMEOUT,
            verbose=False,
        )[0]

        for element in answered:
            mac = element[1].hwsrc.lower()
            discovered[mac] = element

    return list(discovered.values())


def scan(ip_range, scan_run=None):
    ip_range = validate_ip_range(ip_range)
    scan_run = scan_run or ScanRun.objects.create(ip_range=ip_range)
    gateway_ip = get_default_gateway_ip()
    ports_opened = 0
    ports_closed = 0
    new_devices = 0

    try:
        answered_list = discover_devices(ip_range)
        scan_started_at = timezone.now()
        oui = scapy.MANUFDB

        for element in answered_list:
            stats = sync_discovered_device(
                element,
                oui=oui,
                scan_run=scan_run,
                scan_started_at=scan_started_at,
                gateway_ip=gateway_ip,
            )
            new_devices += stats["new_devices"]
            ports_opened += stats["ports_opened"]
            ports_closed += stats["ports_closed"]

        online_macs = [element[1].hwsrc.lower() for element in answered_list]
        clear_stale_gateways(gateway_ip)
        mark_missing_devices_offline(online_macs, scan_run=scan_run)
    except Exception as exc:
        scan_run.status = ScanRun.Status.FAILED
        scan_run.finished_at = timezone.now()
        scan_run.error = str(exc)
        scan_run.save(update_fields=["status", "finished_at", "error"])
        raise

    scan_run.status = ScanRun.Status.SUCCESS
    scan_run.finished_at = timezone.now()
    scan_run.devices_seen = len(answered_list)
    scan_run.new_devices = new_devices
    scan_run.online_devices = Device.objects.filter(online=True).count()
    scan_run.ports_opened = ports_opened
    scan_run.ports_closed = ports_closed
    scan_run.error = ""
    scan_run.save(
        update_fields=[
            "status",
            "finished_at",
            "devices_seen",
            "new_devices",
            "online_devices",
            "ports_opened",
            "ports_closed",
            "error",
        ]
    )
    return scan_run


def sync_discovered_device(element, oui=None, scan_run=None, scan_started_at=None, gateway_ip=""):
    scan_started_at = scan_started_at or timezone.now()
    ip = element[1].psrc
    mac = element[1].hwsrc.lower()
    vendor = ManufDA.lookup(oui, mac) if oui else None
    vendor_name = vendor[1] if vendor else ""
    hostname = get_hostname(ip=ip)
    ports_opened = 0
    ports_closed = 0
    new_devices = 0
    is_gateway = bool(gateway_ip and ip == gateway_ip)

    try:
        device = Device.objects.get(mac=mac)
        was_online = device.online
        update_fields = [
            "ip",
            "online",
            "lastseen",
            "missed_scans",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
        device.ip = ip
        device.online = True
        device.lastseen = scan_started_at
        device.missed_scans = 0
        if hostname and device.hostname != hostname[:255]:
            device.hostname = hostname[:255]
            update_fields.append("hostname")
        if is_gateway and device.role != "gateway":
            device.role = "gateway"
            update_fields.append("role")
        set_device_status(
            device,
            Device.Status.ONLINE,
            Device.StatusSource.ARP,
            now=scan_started_at,
        )
        if is_default_device_name(device.name) or is_default_device_icon(device.icon):
            identity = guess_device_identity(hostname, device.vendor or vendor_name, mac)
            if is_default_device_name(device.name):
                device.name = identity["name"]
                update_fields.append("name")
            if is_default_device_icon(device.icon):
                device.icon = identity["icon"]
                update_fields.append("icon")
        if is_gateway:
            device.is_gateway = True
            device.known = True
            if is_default_device_name(device.name):
                device.name = "Gateway"
            device.icon = "router"
            update_fields.extend(["is_gateway", "known", "name", "icon"])
        device.save(update_fields=update_fields)

        if not was_online:
            create_event(
                NetworkEvent.EventType.DEVICE_ONLINE,
                device=device,
                scan_run=scan_run,
                message=f"{device.name} came online",
            )
    except Device.DoesNotExist:
        identity = guess_device_identity(hostname, vendor_name, mac)
        if is_gateway:
            identity = {
                "name": "Gateway" if is_default_device_name(identity["name"]) else identity["name"],
                "icon": "router",
            }
        device = Device.objects.create(
            icon=identity["icon"],
            name=identity["name"],
            ip=ip,
            mac=mac,
            vendor=vendor_name,
            hostname=hostname[:255] if hostname else "",
            role="gateway" if is_gateway else "device",
            known=is_gateway,
            is_gateway=is_gateway,
            lastseen=scan_started_at,
        )
        set_device_status(
            device,
            Device.Status.ONLINE,
            Device.StatusSource.ARP,
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
        if is_default_device_icon(device.icon):
            device.icon = guess_device_icon(
                hostname=device.name,
                vendor=device.vendor,
                open_ports=open_ports,
            )
            device.save(update_fields=["icon"])
        port_stats = sync_device_ports(device, open_ports, scan_run=scan_run)
        ports_opened += port_stats["ports_opened"]
        ports_closed += port_stats["ports_closed"]
        device.last_port_scan = scan_started_at
        device.save(update_fields=["last_port_scan"])

    return {
        "new_devices": new_devices,
        "ports_opened": ports_opened,
        "ports_closed": ports_closed,
    }


def mark_missing_devices_offline(online_macs, scan_run=None):
    offline_devices = Device.objects.exclude(mac__in=online_macs).filter(online=True)
    for device in offline_devices:
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
