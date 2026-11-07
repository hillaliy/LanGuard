"""Logical-device topology with explicit interface-level connection evidence."""

import hashlib
import json
import re
from datetime import timedelta

from django.utils import timezone

from .datetime_utils import utc_isoformat
from .models import Device, NetworkLink, NetworkLinkDismissal, NetworkMapLayout

STALE_AFTER = timedelta(hours=24)


def link_signature(source, target, source_port="", target_port=""):
    endpoints = sorted([(int(source), source_port.strip()), (int(target), target_port.strip())])
    return hashlib.sha256(json.dumps(endpoints, ensure_ascii=True).encode()).hexdigest()


def endpoint_registry():
    devices = list(Device.objects.filter(archived=False, is_visitor=False).order_by("id"))
    roots = {device.pk: device for device in devices if device.merged_into_id is None}
    interfaces = {device.pk: device for device in devices if (device.merged_into_id or device.pk) in roots}
    return roots, interfaces


def logical_id(device):
    return device.merged_into_id or device.pk


def _text(value):
    return value.strip()[:128] if isinstance(value, str) else ""


def _chassis_mac(value):
    value = _text(value).lower().replace("-", "").replace(":", "").replace(" ", "")
    if not re.fullmatch(r"[0-9a-f]{12}", value) or value == "0" * 12 or int(value[:2], 16) & 1:
        return ""
    return ":".join(value[index:index + 2] for index in range(0, 12, 2))


def lldp_evidence(interfaces):
    by_mac = {device.mac.lower(): device for device in interfaces.values()}
    evidence, unresolved = {}, []
    for source in interfaces.values():
        inventory = source.snmp_data if isinstance(source.snmp_data, dict) else {}
        neighbors = inventory.get("neighbors", [])
        if not isinstance(neighbors, list):
            continue
        for neighbor in neighbors[:200]:
            if not isinstance(neighbor, dict):
                continue
            target = by_mac.get(_chassis_mac(neighbor.get("chassis_id")))
            if not target or not source.snmp_last_seen:
                if len(unresolved) < 200:
                    unresolved.append({"device_id": logical_id(source), "local_port": _text(neighbor.get("local_port")),
                                       "system_name": _text(neighbor.get("system_name")),
                                       "chassis_id": _text(neighbor.get("chassis_id")),
                                       "reason": "No unique inventoried chassis MAC" if not target else "No observation timestamp"})
                continue
            if logical_id(source) == logical_id(target):
                continue
            source_port, target_port = _text(neighbor.get("local_port")), _text(neighbor.get("port_id"))
            key = link_signature(source.pk, target.pk, source_port, target_port)
            existing = evidence.get(key)
            if existing and existing["observed_at"] >= source.snmp_last_seen:
                continue
            evidence[key] = {
                "key": key, "source": source.pk, "target": target.pk,
                "source_device": logical_id(source), "target_device": logical_id(target),
                "source_port": source_port, "target_port": target_port,
                "kind": "unknown", "origin": "lldp", "label": "", "observed_at": source.snmp_last_seen,
            }
    return evidence, unresolved


def network_map_data():
    roots, interfaces = endpoint_registry()
    devices = []
    for root in roots.values():
        members = [device for device in interfaces.values() if logical_id(device) == root.pk]
        devices.append({
            "id": root.pk, "name": root.name or root.hostname or root.ip, "ip": root.ip, "mac": root.mac,
            "icon": root.icon, "secondary_icon": root.secondary_icon, "role": root.role, "room": root.room,
            "online": any(device.online for device in members),
            "interfaces": [{"id": device.pk, "mac": device.mac, "ip": device.ip} for device in members],
        })
    evidence, unresolved = lldp_evidence(interfaces)
    dismissed = set(NetworkLinkDismissal.objects.values_list("key", flat=True))
    links, accepted_keys, signatures = [], set(), set()
    hidden = 0
    now = timezone.now()
    for link in NetworkLink.objects.all():
        source, target = interfaces.get(link.source_id), interfaces.get(link.target_id)
        if not source or not target or logical_id(source) == logical_id(target):
            hidden += 1
            continue
        observation = evidence.get(link.evidence_key)
        seen_at = observation["observed_at"] if observation else link.observed_at
        links.append({
            "id": link.pk, "source": link.source_id, "target": link.target_id,
            "source_device": logical_id(source), "target_device": logical_id(target),
            "source_port": link.source_port, "target_port": link.target_port, "kind": link.kind,
            "label": link.label, "origin": link.origin, "revision": link.revision,
            "observed_at": utc_isoformat(seen_at) if seen_at else None,
            "stale": link.origin == "lldp" and (not observation or not seen_at or now - seen_at > STALE_AFTER),
            "currently_reported": bool(observation) if link.origin == "lldp" else None,
            "updated_at": utc_isoformat(link.updated_at),
        })
        accepted_keys.add(link.evidence_key)
        signatures.add(link.signature)
    suggestions = []
    for key, item in evidence.items():
        if key in dismissed or key in accepted_keys or key in signatures:
            continue
        suggestions.append({**item, "observed_at": utc_isoformat(item["observed_at"]),
                            "stale": now - item["observed_at"] > STALE_AFTER})
    layout = NetworkMapLayout.objects.filter(pk=1).first()
    return {
        "devices": devices, "links": links, "suggestions": suggestions, "unresolved": unresolved,
        "hidden_links": hidden, "dismissed_count": len(dismissed),
        "layout": {"positions": layout.positions if layout else {}, "revision": layout.revision if layout else 0},
    }


def record_network_observations():
    """Refresh evidence timestamps during scanning without touching user edits."""
    if not NetworkLink.objects.filter(origin="lldp").exists():
        return
    _, interfaces = endpoint_registry()
    evidence, _ = lldp_evidence(interfaces)
    for key, item in evidence.items():
        NetworkLink.objects.filter(origin="lldp", evidence_key=key).filter(
            observed_at__lt=item["observed_at"],
        ).update(observed_at=item["observed_at"])
