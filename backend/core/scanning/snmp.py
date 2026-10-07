import ipaddress
import logging
import random
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

from scapy.asn1.asn1 import ASN1_NULL
from scapy.layers.snmp import SNMP, SNMPget, SNMPnext, SNMPvarbind

from .identity import clean_hostname


LOGGER = logging.getLogger(__name__)
SYSTEM_OIDS = {
    "description": "1.3.6.1.2.1.1.1.0",
    "object_id": "1.3.6.1.2.1.1.2.0",
    "uptime_ticks": "1.3.6.1.2.1.1.3.0",
    "contact": "1.3.6.1.2.1.1.4.0",
    "name": "1.3.6.1.2.1.1.5.0",
    "location": "1.3.6.1.2.1.1.6.0",
    "services": "1.3.6.1.2.1.1.7.0",
}
INTERFACE_OIDS = {
    "description": "1.3.6.1.2.1.2.2.1.2",
    "type": "1.3.6.1.2.1.2.2.1.3",
    "speed_bps": "1.3.6.1.2.1.2.2.1.5",
    "mac": "1.3.6.1.2.1.2.2.1.6",
    "admin_status": "1.3.6.1.2.1.2.2.1.7",
    "oper_status": "1.3.6.1.2.1.2.2.1.8",
    "name": "1.3.6.1.2.1.31.1.1.1.1",
    "high_speed_mbps": "1.3.6.1.2.1.31.1.1.1.15",
}
LLDP_LOCAL_OIDS = {
    "port_id": "1.0.8802.1.1.2.1.3.7.1.3",
    "description": "1.0.8802.1.1.2.1.3.7.1.4",
}
LLDP_REMOTE_OIDS = {
    "chassis_id": "1.0.8802.1.1.2.1.4.1.1.5",
    "port_id": "1.0.8802.1.1.2.1.4.1.1.7",
    "system_name": "1.0.8802.1.1.2.1.4.1.1.9",
    "system_description": "1.0.8802.1.1.2.1.4.1.1.10",
}
HOST_DEVICE_TYPE_OID = "1.3.6.1.2.1.25.3.2.1.2"
HOST_PRINTER_DEVICE_TYPE = "1.3.6.1.2.1.25.3.1.5"
INTERFACE_TYPES = {
    6: "Ethernet",
    24: "Loopback",
    53: "Virtual",
    71: "Wi-Fi",
    131: "Tunnel",
    135: "VLAN",
    161: "Link aggregation",
}
STATUS_VALUES = {1: "up", 2: "down", 3: "testing"}
VENDOR_NAMES = {
    "aruba": "Aruba",
    "brother": "Brother",
    "canon": "Canon",
    "cisco": "Cisco",
    "epson": "Epson",
    "hewlett packard": "HP",
    "hpe": "HPE",
    "hp ": "HP",
    "mikrotik": "MikroTik",
    "netgear": "NETGEAR",
    "openwrt": "OpenWrt",
    "ruckus": "Ruckus",
    "tp-link": "TP-Link",
    "ubiquiti": "Ubiquiti",
    "unifi": "Ubiquiti",
    "xerox": "Xerox",
}


def normalize_oid(value):
    return str(value or "").strip().lstrip(".")


def oid_suffix(oid, base_oid):
    oid = normalize_oid(oid)
    base_oid = normalize_oid(base_oid)
    prefix = f"{base_oid}."
    return oid[len(prefix) :] if oid.startswith(prefix) else ""


def snmp_value(value, *, mac=False):
    raw = getattr(value, "val", value)
    if raw is None or value.__class__.__name__ in {
        "ASN1_NULL",
        "ASN1_NO_SUCH_OBJECT",
        "ASN1_NO_SUCH_INSTANCE",
        "ASN1_END_OF_MIB_VIEW",
    }:
        return None
    if isinstance(raw, bytes):
        if mac and len(raw) == 6:
            return ":".join(f"{byte:02x}" for byte in raw)
        decoded = raw.decode("utf-8", "replace").strip().strip('"')
        return decoded if decoded and "\ufffd" not in decoded else raw.hex()
    if isinstance(raw, (int, float)):
        return raw
    return str(raw).strip().lstrip(".")


def snmp_exchange(ip, community, oids, *, next_request=False, timeout=0.4):
    request_id = random.randint(1, 2_147_483_647)
    pdu_class = SNMPnext if next_request else SNMPget
    packet = SNMP(
        version=1,
        community=community,
        PDU=pdu_class(
            id=request_id,
            varbindlist=[
                SNMPvarbind(oid=normalize_oid(oid), value=ASN1_NULL(0)) for oid in oids
            ],
        ),
    )
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(bytes(packet), (ip, 161))
            payload, source = sock.recvfrom(65_535)
    except (OSError, ValueError):
        return []
    if source[0] != ip:
        return []
    try:
        response = SNMP(payload)
        if int(response.PDU.id.val) != request_id or int(response.PDU.error.val):
            return []
    except (AttributeError, TypeError, ValueError):
        return []
    return [
        (normalize_oid(varbind.oid.val), varbind.value)
        for varbind in response.PDU.varbindlist
    ]


def snmp_get(ip, community, oid_map, *, timeout=0.4):
    names = list(oid_map)
    response = snmp_exchange(
        ip,
        community,
        [oid_map[name] for name in names],
        timeout=timeout,
    )
    values = {}
    for name, (oid, value) in zip(names, response):
        if normalize_oid(oid) != normalize_oid(oid_map[name]):
            continue
        normalized = snmp_value(value, mac=name == "mac")
        if normalized not in (None, ""):
            values[name] = normalized
    return values


def snmp_walk_columns(ip, community, oid_map, *, timeout=0.4, max_rows=48):
    cursors = {name: normalize_oid(oid) for name, oid in oid_map.items()}
    active = list(oid_map)
    rows = {name: {} for name in oid_map}
    for _ in range(max_rows):
        if not active:
            break
        response = snmp_exchange(
            ip,
            community,
            [cursors[name] for name in active],
            next_request=True,
            timeout=timeout,
        )
        if len(response) != len(active):
            break
        next_active = []
        for name, (returned_oid, value) in zip(active, response):
            suffix = oid_suffix(returned_oid, oid_map[name])
            if not suffix or returned_oid == cursors[name]:
                continue
            normalized = snmp_value(value, mac=name in {"mac", "chassis_id"})
            if normalized not in (None, ""):
                rows[name][suffix] = normalized
            cursors[name] = returned_oid
            next_active.append(name)
        active = next_active
    return rows


def interface_inventory(columns):
    indexes = sorted(
        {suffix for values in columns.values() for suffix in values},
        key=lambda value: tuple(
            int(part) for part in value.split(".") if part.isdigit()
        ),
    )
    interfaces = []
    for index in indexes:
        name = str(columns.get("name", {}).get(index) or "").strip()
        description = str(columns.get("description", {}).get(index) or "").strip()
        if not name and not description:
            continue
        interface_type = columns.get("type", {}).get(index)
        high_speed = columns.get("high_speed_mbps", {}).get(index)
        speed_bps = columns.get("speed_bps", {}).get(index)
        try:
            speed_mbps = int(high_speed or 0) or int(speed_bps or 0) // 1_000_000
        except TypeError, ValueError:
            speed_mbps = 0
        try:
            type_label = INTERFACE_TYPES.get(
                int(interface_type), str(interface_type or "")
            )
        except TypeError, ValueError:
            type_label = str(interface_type or "")
        interfaces.append(
            {
                "index": int(index) if index.isdigit() else index,
                "name": name or description,
                "description": description,
                "type": type_label,
                "speed_mbps": speed_mbps,
                "mac": columns.get("mac", {}).get(index, ""),
                "admin_status": STATUS_VALUES.get(
                    columns.get("admin_status", {}).get(index), "unknown"
                ),
                "oper_status": STATUS_VALUES.get(
                    columns.get("oper_status", {}).get(index), "unknown"
                ),
            }
        )
    return interfaces


def lldp_neighbors(local_columns, remote_columns):
    local_ports = {}
    for field in ("port_id", "description"):
        for index, value in local_columns.get(field, {}).items():
            local_ports.setdefault(index, {})[field] = value

    neighbors = []
    indexes = sorted(
        {suffix for values in remote_columns.values() for suffix in values}
    )
    for index in indexes:
        parts = index.split(".")
        local_index = parts[-2] if len(parts) >= 2 else ""
        local_port = local_ports.get(local_index, {})
        neighbor = {
            "local_port": local_port.get("port_id")
            or local_port.get("description")
            or local_index,
            "chassis_id": remote_columns.get("chassis_id", {}).get(index, ""),
            "port_id": remote_columns.get("port_id", {}).get(index, ""),
            "system_name": remote_columns.get("system_name", {}).get(index, ""),
            "system_description": remote_columns.get("system_description", {}).get(
                index, ""
            ),
        }
        if any(neighbor.values()):
            neighbors.append(neighbor)
    return neighbors


def snmp_vendor(description):
    lowered = str(description or "").lower()
    for marker, vendor in VENDOR_NAMES.items():
        if marker in lowered:
            return vendor
    return ""


def classify_snmp_device(system, neighbors, host_device_types):
    text = " ".join(
        str(system.get(field) or "") for field in ("description", "object_id", "name")
    ).lower()
    if HOST_PRINTER_DEVICE_TYPE in host_device_types or any(
        marker in text for marker in ("printer", "laserjet", "imageclass")
    ):
        return "printer"
    if any(
        marker in text
        for marker in ("access point", "wireless ap", "wifi ap", "air-ap", "uap-")
    ):
        return "access_point"
    if neighbors or any(
        marker in text
        for marker in ("switch", "bridge", "catalyst", "procurve", "usw-")
    ):
        return "switch"
    if any(marker in text for marker in ("router", "gateway", "openwrt", "routeros")):
        return "router"
    return "managed_device"


def collect_snmp_inventory(
    ip, community, *, timeout=0.4, max_interfaces=48, max_neighbors=32
):
    timeout = max(0.1, min(float(timeout), 5.0))
    max_interfaces = max(1, min(int(max_interfaces), 256))
    max_neighbors = max(1, min(int(max_neighbors), 256))
    system = snmp_get(ip, community, SYSTEM_OIDS, timeout=timeout)
    if not system:
        return None
    system["name"] = clean_hostname(str(system.get("name") or ""), ip_address=ip)
    interfaces = interface_inventory(
        snmp_walk_columns(
            ip,
            community,
            INTERFACE_OIDS,
            timeout=timeout,
            max_rows=max_interfaces,
        )
    )[:max_interfaces]
    local_lldp = snmp_walk_columns(
        ip,
        community,
        LLDP_LOCAL_OIDS,
        timeout=timeout,
        max_rows=max_neighbors,
    )
    remote_lldp = snmp_walk_columns(
        ip,
        community,
        LLDP_REMOTE_OIDS,
        timeout=timeout,
        max_rows=max_neighbors,
    )
    neighbors = lldp_neighbors(local_lldp, remote_lldp)[:max_neighbors]
    host_devices = snmp_walk_columns(
        ip,
        community,
        {"type": HOST_DEVICE_TYPE_OID},
        timeout=timeout,
        max_rows=16,
    )["type"]
    host_device_types = {normalize_oid(value) for value in host_devices.values()}
    return {
        "device_type": classify_snmp_device(system, neighbors, host_device_types),
        "vendor": snmp_vendor(system.get("description")),
        "system": system,
        "interfaces": interfaces,
        "neighbors": neighbors,
    }


def discover_snmp_inventory(
    ip_addresses,
    community,
    *,
    timeout=0.4,
    max_devices=64,
    max_interfaces=48,
    max_neighbors=32,
    concurrency=8,
):
    if not community or int(max_devices) <= 0:
        return {}
    timeout = max(0.1, min(float(timeout), 5.0))
    max_devices = min(int(max_devices), 1024)
    max_interfaces = max(1, min(int(max_interfaces), 256))
    max_neighbors = max(1, min(int(max_neighbors), 256))
    concurrency = max(1, min(int(concurrency), 32))
    addresses = []
    for value in set(ip_addresses):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.version == 4 and (address.is_private or address.is_link_local):
            addresses.append(address)
    targets = []
    for address in sorted(addresses):
        targets.append(str(address))
        if len(targets) >= max_devices:
            break
    if not targets:
        return {}

    inventory = {}
    with ThreadPoolExecutor(
        max_workers=min(concurrency, len(targets))
    ) as executor:
        futures = {
            executor.submit(
                collect_snmp_inventory,
                ip,
                community,
                timeout=timeout,
                max_interfaces=max_interfaces,
                max_neighbors=max_neighbors,
            ): ip
            for ip in targets
        }
        for future in as_completed(futures):
            ip = futures[future]
            try:
                metadata = future.result()
            except Exception:
                LOGGER.exception("SNMP inventory collection failed for %s", ip)
                continue
            if metadata:
                inventory[ip] = metadata
    return inventory
