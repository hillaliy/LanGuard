from django.db.models import Q
from django.utils import timezone

from ..models import Device
from ..scanning.identity import guess_device_identity, validated_hostname
from ..scanning.reconciliation import IP_IDENTITY_CONFLICT_MARKER, IP_IDENTITY_CONFLICT_WINDOW


def apply_client_observations(
    leases, observed_at, create_devices, *, identity_source=Device.IdentitySource.DHCP,
    observation_reason="Observed in DHCP lease source",
):
    summary = {"devices_discovered": 0, "devices_updated": 0, "devices_skipped": 0, "identity_conflicts": 0}
    by_mac = {}
    for lease in leases:
        by_mac.setdefault(lease["mac"], []).append(lease)
    for mac, records in by_mac.items():
        if len(records) != 1:
            summary["devices_skipped"] += len(records)
            continue
        lease = {**records[0], "name": validated_hostname(records[0]["name"], mac)}
        device = Device.objects.filter(mac=mac).first()
        if device and device.archived:
            summary["devices_skipped"] += 1
            continue
        if device and device.ip != lease["ip"] and (
            device.lastseen > observed_at or device.ip_assignments.filter(valid_from__gt=observed_at).exists()
        ):
            summary["devices_skipped"] += 1
            continue
        competing = Device.objects.filter(ip=lease["ip"], archived=False).exclude(mac=mac).filter(
            Q(lastseen__gte=timezone.now() - IP_IDENTITY_CONFLICT_WINDOW)
            | Q(ip_assignments__ip=lease["ip"], ip_assignments__valid_from__gt=observed_at,
                ip_assignments__valid_until__isnull=True)
        ).distinct()
        if competing.exists():
            macs = sorted({mac, *competing.values_list("mac", flat=True)})[:4]
            reason = f"IP {lease['ip']}{IP_IDENTITY_CONFLICT_MARKER}{', '.join(macs)}"
            ids = [*competing.values_list("pk", flat=True), *([device.pk] if device else [])]
            Device.objects.filter(pk__in=ids).filter(
                Q(identity_conflict_detected_at__isnull=True)
                | Q(identity_conflict_detected_at__lte=observed_at)
            ).update(identity_conflict_reason=reason, identity_conflict_detected_at=observed_at)
            summary["identity_conflicts"] += 1
            continue
        if device is None:
            if not create_devices:
                summary["devices_skipped"] += 1
                continue
            identity = guess_device_identity(hostname=lease["name"], mac=mac)
            device = Device(
                mac=mac, ip=lease["ip"], hostname=lease["name"], name=identity["name"], icon=identity["icon"],
                hostname_source=identity_source if lease["name"] else "",
                online=False, status=Device.Status.RECENTLY_SEEN, status_source=Device.StatusSource.RECENT,
                status_reason=observation_reason, firstseen=observed_at,
                lastseen=observed_at, last_status_check=observed_at,
            )
            device.save(ip_observed_at=observed_at)
            summary["devices_discovered"] += 1
            continue
        fields = []
        if device.ip != lease["ip"]:
            device.ip = lease["ip"]
            fields.append("ip")
        if not device.known and lease["name"] and device.hostname_source in {
            "", Device.IdentitySource.DHCP, Device.IdentitySource.INFERRED, Device.IdentitySource.IMPORTED,
            identity_source,
        } and device.hostname != lease["name"]:
            device.hostname = lease["name"]
            device.hostname_source = identity_source
            fields.extend(["hostname", "hostname_source"])
            if not device.name or device.name == "Device":
                device.name = guess_device_identity(hostname=lease["name"], mac=mac)["name"]
                fields.append("name")
        if fields:
            device.save(update_fields=fields, ip_observed_at=observed_at)
            summary["devices_updated"] += 1
    return summary
