import logging
import ipaddress
import socket

from django.conf import settings
from django.utils import timezone
import scapy.all as scapy
from scapy.data import ManufDA

from .models import Device, DevicePort, NetworkEvent, ScanRun
from .notifications import notify_event


LOGGER = logging.getLogger(__name__)
DEFAULT_DEVICE_NAME = "Device"
DEFAULT_DEVICE_ICONS = {"", "plus", "unknown", "device", "desktop"}


def get_hostname(ip):
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return clean_hostname(hostname)
    except socket.herror as e:
        LOGGER.debug("Hostname lookup failed for %s: %s", ip, e)
        return DEFAULT_DEVICE_NAME


def clean_hostname(hostname):
    hostname = (hostname or "").strip().rstrip(".")
    if not hostname:
        return DEFAULT_DEVICE_NAME
    return hostname.split(".")[0].replace("-", " ").strip() or DEFAULT_DEVICE_NAME


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


def device_mac_suffix(mac):
    return (mac or "").replace(":", "")[-4:].upper()


def is_default_device_name(name):
    cleaned = (name or "").strip().lower()
    return not cleaned or cleaned == DEFAULT_DEVICE_NAME.lower()


def is_default_device_icon(icon):
    return (icon or "").strip().lower() in DEFAULT_DEVICE_ICONS


def guess_device_icon(hostname="", vendor="", open_ports=None):
    text = f"{hostname} {vendor}".lower().replace("-", " ").replace("_", " ")
    open_port_numbers = {int(port["port"]) for port in open_ports or []}

    if any(keyword in text for keyword in ("smart hub", "home hub")) or (
        any(keyword in text for keyword in ("aqara", "aqura")) and any(keyword in text for keyword in ("hub", "gateway"))
    ):
        return "smart-hub"
    if any(
        keyword in text
        for keyword in ("router", "gateway", "tp link", "tp-link", "tplink", "ubiquiti", "mikrotik", "deco")
    ):
        return "router"
    if any(keyword in text for keyword in ("iphone", "android", "phone", "mobile", "oneplus", "pixel")):
        return "phone"
    if any(keyword in text for keyword in ("macbook", "laptop", "notebook")):
        return "laptop"
    if any(keyword in text for keyword in ("apple tv", "chromecast", "streamer", "streaming", "roku", "fire tv")):
        return "streamer"
    if any(keyword in text for keyword in ("tv", "television")):
        return "tv"
    if any(keyword in text for keyword in ("camera", "cam", "hikvision", "dahua")) or 554 in open_port_numbers:
        return "security-camera"
    if any(keyword in text for keyword in ("shutter", "blind", "blinds", "shade", "curtain")):
        return "shutter"
    if any(keyword in text for keyword in ("led strip", "light strip", "strip light")):
        return "led-strip"
    if any(keyword in text for keyword in ("desk lamp", "table lamp", "reading lamp")):
        return "desk-lamp"
    if any(keyword in text for keyword in ("ceiling light", "downlight")):
        return "ceiling-light"
    if any(keyword in text for keyword in ("light", "bulb", "lamp")):
        return "light"
    if any(keyword in text for keyword in ("air conditioner", "air-conditioning", "aircon", "hvac")):
        return "air-conditioner"
    if any(keyword in text for keyword in ("thermostat", "heater")):
        return "thermostat"
    if any(keyword in text for keyword in ("speaker", "sonos", "homepod", "audio")):
        return "speaker"
    if (
        any(keyword in text for keyword in ("printer", "canon", "brother", "epson", "hewlett", "hp"))
        or 9100 in open_port_numbers
    ):
        return "printer"
    if (
        any(keyword in text for keyword in ("server", "nas", "casaos", "raspberry", "linux"))
        or {22, 80, 443} & open_port_numbers
    ):
        return "server"
    return "unknown"


def guess_device_name(hostname, vendor, mac):
    if hostname and not is_default_device_name(hostname):
        return hostname
    if vendor:
        vendor_name = short_vendor(vendor)
        suffix = device_mac_suffix(mac)
        return f"{vendor_name} device {suffix}" if suffix else f"{vendor_name} device"
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
            )
            new_devices += stats["new_devices"]
            ports_opened += stats["ports_opened"]
            ports_closed += stats["ports_closed"]

        online_macs = [element[1].hwsrc.lower() for element in answered_list]
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


def sync_discovered_device(element, oui=None, scan_run=None, scan_started_at=None):
    scan_started_at = scan_started_at or timezone.now()
    ip = element[1].psrc
    mac = element[1].hwsrc.lower()
    vendor = ManufDA.lookup(oui, mac) if oui else None
    vendor_name = vendor[1] if vendor else ""
    hostname = get_hostname(ip=ip)
    ports_opened = 0
    ports_closed = 0
    new_devices = 0

    try:
        device = Device.objects.get(mac=mac)
        was_online = device.online
        update_fields = ["ip", "online", "lastseen", "missed_scans"]
        device.ip = ip
        device.online = True
        device.lastseen = scan_started_at
        device.missed_scans = 0
        if is_default_device_name(device.name) or is_default_device_icon(device.icon):
            identity = guess_device_identity(hostname, device.vendor or vendor_name, mac)
            if is_default_device_name(device.name):
                device.name = identity["name"]
                update_fields.append("name")
            if is_default_device_icon(device.icon):
                device.icon = identity["icon"]
                update_fields.append("icon")
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
        device = Device.objects.create(
            icon=identity["icon"],
            name=identity["name"],
            ip=ip,
            mac=mac,
            vendor=vendor_name,
            lastseen=scan_started_at,
        )
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
        device.missed_scans += 1
        if device.missed_scans < settings.SCAN_OFFLINE_AFTER_MISSES:
            device.save(update_fields=["missed_scans"])
            continue

        device.online = False
        device.save(update_fields=["online", "missed_scans"])
        create_event(
            NetworkEvent.EventType.DEVICE_OFFLINE,
            device=device,
            scan_run=scan_run,
            message=f"{device.name} went offline",
        )
