import socket

from django.conf import settings
from django.utils import timezone

from ..models import DevicePort, NetworkEvent
from .events import create_event


def get_service_name(port, protocol="tcp"):
    try:
        return socket.getservbyport(port, protocol)
    except OSError:
        return ""

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

def sync_device_ports(device, open_ports, scan_run=None, scanned_ports=None):
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

    open_port_queryset = device.ports.filter(open=True)
    if scanned_ports is not None:
        open_port_queryset = open_port_queryset.filter(port__in=scanned_ports)

    for device_port in open_port_queryset:
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
