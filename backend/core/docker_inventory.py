import http.client
import ipaddress
import json
import os
import socket
from datetime import timezone as datetime_timezone
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Device, DockerContainer, DockerHost, NetworkEvent


DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
MAX_CONTAINERS = 2000


class DockerInventoryError(Exception):
    pass


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__("localhost", timeout=15)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def _docker_get(path):
    connection = UnixHTTPConnection(DOCKER_SOCKET)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        body = response.read()
    except (OSError, http.client.HTTPException) as exc:
        raise DockerInventoryError(
            "Docker is unavailable. Mount /var/run/docker.sock into the scheduler service."
        ) from exc
    finally:
        connection.close()
    if response.status != 200:
        raise DockerInventoryError("Docker Engine returned an error while reading inventory.")
    try:
        return json.loads(body)
    except (TypeError, ValueError) as exc:
        raise DockerInventoryError("Docker Engine returned invalid inventory data.") from exc


def _container_payload(summary):
    container_id = str(summary.get("Id") or "")
    detail = _docker_get(f"/containers/{quote(container_id, safe='')}/json")
    config = detail.get("Config") or {}
    state = detail.get("State") or {}
    network_settings = detail.get("NetworkSettings") or {}
    addresses = []
    for network_name, network in (network_settings.get("Networks") or {}).items():
        network = network or {}
        driver = ""
        network_id = network.get("NetworkID")
        if network_id:
            try:
                driver = str(
                    _docker_get(f"/networks/{quote(str(network_id), safe='')}").get("Driver")
                    or ""
                )
            except DockerInventoryError:
                driver = ""
        if network.get("IPAddress"):
            addresses.append(
                {
                    "network": str(network_name),
                    "driver": driver,
                    "ip": str(network.get("IPAddress")),
                    "mac": str(network.get("MacAddress") or ""),
                }
            )

    published_ports = []
    for container_port, bindings in (network_settings.get("Ports") or {}).items():
        port_text, _, protocol = str(container_port).partition("/")
        for binding in bindings or []:
            if not binding.get("HostPort"):
                continue
            published_ports.append(
                {
                    "container_port": int(port_text),
                    "host_ip": str(binding.get("HostIp") or ""),
                    "host_port": int(binding["HostPort"]),
                    "protocol": protocol or "tcp",
                }
            )

    health = state.get("Health") or {}
    return {
        "id": container_id,
        "name": str(detail.get("Name") or "").lstrip("/"),
        "image": str(config.get("Image") or ""),
        "image_id": str(detail.get("Image") or ""),
        "state": str(state.get("Status") or ""),
        "health": str(health.get("Status") or ""),
        "status": str(summary.get("Status") or ""),
        "network_mode": str((detail.get("HostConfig") or {}).get("NetworkMode") or ""),
        "addresses": addresses,
        "published_ports": published_ports,
        "started_at": state.get("StartedAt"),
        "restart_count": int(detail.get("RestartCount") or 0),
    }


def collect_local_inventory():
    info = _docker_get("/info")
    containers = _docker_get("/containers/json?all=0")
    if not isinstance(info, dict) or not isinstance(containers, list):
        raise DockerInventoryError("Docker Engine returned invalid inventory data.")
    if len(containers) > MAX_CONTAINERS:
        raise DockerInventoryError("Docker Engine returned too many containers.")
    try:
        container_inventory = [_container_payload(item) for item in containers]
    except (KeyError, TypeError, ValueError) as exc:
        raise DockerInventoryError("Docker Engine returned invalid container data.") from exc
    return {
        "host": {
            "name": str(info.get("Name") or ""),
            "docker_version": str(info.get("ServerVersion") or ""),
            "operating_system": str(info.get("OperatingSystem") or ""),
            "architecture": str(info.get("Architecture") or ""),
        },
        "containers": container_inventory,
    }


def _text(value, limit):
    return str(value or "").strip()[:limit]


def _datetime(value):
    parsed = parse_datetime(str(value or ""))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    if not settings.USE_TZ:
        return timezone.make_naive(parsed, datetime_timezone.utc)
    return parsed


def _non_negative_int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _addresses(value):
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:64]:
        if not isinstance(item, dict):
            continue
        ip = _text(item.get("ip"), 64)
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        result.append(
            {
                "network": _text(item.get("network"), 128),
                "driver": _text(item.get("driver"), 32),
                "ip": ip,
                "mac": _text(item.get("mac"), 17).lower(),
            }
        )
    return result


def _published_ports(value):
    if not isinstance(value, list):
        return []
    result = []
    seen = set()
    for item in value[:256]:
        if not isinstance(item, dict):
            continue
        try:
            container_port = int(item.get("container_port"))
            host_port = int(item.get("host_port"))
        except (TypeError, ValueError):
            continue
        protocol = _text(item.get("protocol") or "tcp", 8).lower()
        if not (1 <= container_port <= 65535 and 1 <= host_port <= 65535):
            continue
        key = (container_port, host_port, protocol)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "container_port": container_port,
                "host_ip": _text(item.get("host_ip"), 64),
                "host_port": host_port,
                "protocol": protocol,
            }
        )
    return sorted(result, key=lambda item: (item["host_port"], item["protocol"]))


def _linked_device(addresses, network_mode):
    independent = network_mode in {"macvlan", "ipvlan"} or any(
        address.get("driver") in {"macvlan", "ipvlan"} for address in addresses
    )
    if not independent:
        return None
    ips = [address["ip"] for address in addresses]
    return Device.objects.filter(ip__in=ips, archived=False).order_by("id").first()


@transaction.atomic
def apply_docker_inventory(host, payload):
    now = timezone.now()
    info = payload.get("host") if isinstance(payload.get("host"), dict) else {}
    host.docker_name = _text(info.get("name"), 255)
    host.docker_version = _text(info.get("docker_version"), 64)
    host.operating_system = _text(info.get("operating_system"), 255)
    host.architecture = _text(info.get("architecture"), 64)
    host.last_sync_at = now
    host.last_error = ""
    host.save(
        update_fields=[
            "docker_name",
            "docker_version",
            "operating_system",
            "architecture",
            "last_sync_at",
            "last_error",
            "updated_at",
        ]
    )

    observed_ids = set()
    created_count = 0
    exposed_count = 0
    for raw in payload["containers"]:
        if not isinstance(raw, dict):
            continue
        container_id = _text(raw.get("id"), 64)
        name = _text(raw.get("name"), 255)
        if not container_id or not name:
            continue
        observed_ids.add(container_id)
        addresses = _addresses(raw.get("addresses"))
        ports = _published_ports(raw.get("published_ports"))
        network_mode = _text(raw.get("network_mode"), 64).lower()
        existing = DockerContainer.objects.filter(
            host=host,
            container_id=container_id,
        ).first()
        previous_ports = existing.published_ports if existing else []
        container, created = DockerContainer.objects.update_or_create(
            host=host,
            container_id=container_id,
            defaults={
                "linked_device": _linked_device(addresses, network_mode),
                "name": name,
                "image": _text(raw.get("image"), 512),
                "image_id": _text(raw.get("image_id"), 255),
                "state": _text(raw.get("state"), 32).lower(),
                "health": _text(raw.get("health"), 32).lower(),
                "status": _text(raw.get("status"), 255),
                "network_mode": network_mode,
                "addresses": addresses,
                "published_ports": ports,
                "started_at": _datetime(raw.get("started_at")),
                "restart_count": _non_negative_int(raw.get("restart_count")),
                "active": True,
                "last_seen": now,
            },
        )
        if created:
            created_count += 1
            NetworkEvent.objects.create(
                device=host.device,
                event_type=NetworkEvent.EventType.CONTAINER_DISCOVERED,
                message=f"Container {container.name} was discovered on {host.name}"[:255],
                metadata={"container_id": container.container_id, "container": container.name},
                notified=True,
            )
        previous_keys = {
            (item.get("host_port"), item.get("protocol"))
            for item in previous_ports
            if isinstance(item, dict)
        }
        new_ports = [] if created else [
            item
            for item in ports
            if (item["host_port"], item["protocol"]) not in previous_keys
        ]
        for port in new_ports:
            exposed_count += 1
            NetworkEvent.objects.create(
                device=host.device,
                event_type=NetworkEvent.EventType.CONTAINER_PORT_EXPOSED,
                message=(
                    f"Container {container.name} published "
                    f"{port['protocol']}/{port['host_port']} on {host.name}"
                )[:255],
                metadata={"container_id": container.container_id, "container": container.name, **port},
                notified=True,
            )

    DockerContainer.objects.filter(host=host, active=True).exclude(
        container_id__in=observed_ids
    ).update(active=False)
    return {
        "containers": len(observed_ids),
        "new_containers": created_count,
        "new_published_ports": exposed_count,
    }


def sync_docker_host(host):
    try:
        payload = collect_local_inventory()
        return apply_docker_inventory(host, payload)
    except DockerInventoryError as exc:
        host.last_error = str(exc)[:255]
        host.save(update_fields=["last_error", "updated_at"])
        raise


def sync_enabled_docker_hosts():
    now = timezone.now()
    results = []
    for host in DockerHost.objects.filter(enabled=True).select_related("device"):
        if host.last_sync_at and not host.sync_requested:
            elapsed = (now - host.last_sync_at).total_seconds()
            if elapsed < max(host.sync_interval, 1) * 60:
                continue
        try:
            results.append({"host": host.id, "status": "ok", **sync_docker_host(host)})
        except DockerInventoryError:
            results.append({"host": host.id, "status": "error"})
        finally:
            DockerHost.objects.filter(pk=host.pk).update(sync_requested=False)
    return results
