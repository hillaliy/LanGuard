from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Device, NetworkEvent


STATUS_PRIORITY = {
    Device.Status.ONLINE: 0,
    Device.Status.RECENTLY_SEEN: 1,
    Device.Status.SLEEPING: 2,
    Device.Status.OFFLINE: 3,
}


def primary_device(device):
    return device.merged_into or device


def device_interfaces(device):
    root = primary_device(device)
    prefetched = getattr(root, "_prefetched_objects_cache", {}).get(
        "merged_interfaces"
    )
    children = (
        list(prefetched)
        if prefetched is not None
        else list(root.merged_interfaces.all())
    )
    return [root, *children]


def effective_device_state(device):
    interfaces = device_interfaces(device)
    representative = min(
        interfaces,
        key=lambda item: (
            STATUS_PRIORITY.get(item.status, 99),
            -item.lastseen.timestamp(),
            item.id,
        ),
    )
    return {
        "online": any(item.online for item in interfaces),
        "status": representative.status,
        "status_display": representative.get_status_display(),
        "status_source": representative.status_source,
        "status_source_display": representative.get_status_source_display(),
        "status_reason": representative.status_reason,
        "firstseen": min(item.firstseen for item in interfaces),
        "lastseen": max(item.lastseen for item in interfaces),
        "last_status_check": max(
            (item.last_status_check for item in interfaces if item.last_status_check),
            default=None,
        ),
        "last_port_scan": max(
            (item.last_port_scan for item in interfaces if item.last_port_scan),
            default=None,
        ),
        "missed_scans": min(item.missed_scans for item in interfaces),
    }


def group_device_ids(device):
    root = primary_device(device)
    return [root.id, *root.merged_interfaces.values_list("id", flat=True)]


def logical_online_device_count():
    roots = Device.objects.filter(
        archived=False,
        merged_into__isnull=True,
    ).prefetch_related("merged_interfaces")
    return sum(effective_device_state(item)["online"] for item in roots)


@transaction.atomic
def merge_device_interfaces(target_id, source_ids, user):
    source_ids = list(dict.fromkeys(source_ids))
    if not source_ids:
        raise ValidationError({"source_ids": "Choose at least one device to merge."})
    if target_id in source_ids:
        raise ValidationError(
            {"source_ids": "The primary device cannot merge into itself."}
        )

    devices = {
        item.id: item
        for item in Device.objects.select_for_update()
        .select_related("merged_into")
        .filter(id__in=[target_id, *source_ids])
    }
    if target_id not in devices or any(
        source_id not in devices for source_id in source_ids
    ):
        raise ValidationError(
            {"source_ids": "One or more selected devices no longer exist."}
        )

    target = devices[target_id]
    if target.merged_into_id:
        raise ValidationError(
            {"target_id": "Choose a primary device, not a merged interface."}
        )
    if target.archived:
        raise ValidationError(
            {"target_id": "Archived devices cannot receive interfaces."}
        )

    now = timezone.now()
    merged_ids = []
    for source_id in source_ids:
        source = devices[source_id]
        if source.archived:
            raise ValidationError(
                {"source_ids": "Restore archived devices before merging them."}
            )
        if source.merged_into_id:
            raise ValidationError(
                {"source_ids": f"{source.name} is already part of another device."}
            )

        descendants = list(
            Device.objects.select_for_update().filter(merged_into=source)
        )
        members = [source, *descendants]
        for member in members:
            member.merged_into = target
            member.merged_at = now
            member.merged_by = user
        Device.objects.bulk_update(
            members,
            ["merged_into", "merged_at", "merged_by"],
        )
        merged_ids.extend(member.id for member in members)

    NetworkEvent.objects.create(
        device=target,
        event_type=NetworkEvent.EventType.DEVICE_INTERFACES_MERGED,
        message=(
            f"{len(merged_ids)} network interface"
            f"{'s were' if len(merged_ids) != 1 else ' was'} merged into {target.name}"
        ),
        metadata={"interface_device_ids": merged_ids},
        notified=True,
    )
    return target


@transaction.atomic
def unmerge_device_interface(target_id, interface_id, user):
    devices = {
        item.id: item
        for item in Device.objects.select_for_update().filter(
            id__in=[target_id, interface_id]
        )
    }
    target = devices.get(target_id)
    interface = devices.get(interface_id)
    if not target or not interface or interface.merged_into_id != target_id:
        raise ValidationError(
            {"interface_id": "This interface does not belong to the selected device."}
        )

    interface.merged_into = None
    interface.merged_at = None
    interface.merged_by = None
    interface.save(update_fields=["merged_into", "merged_at", "merged_by"])
    NetworkEvent.objects.create(
        device=target,
        event_type=NetworkEvent.EventType.DEVICE_INTERFACE_SEPARATED,
        message=f"The {interface.mac} interface was separated from {target.name}",
        metadata={
            "interface_device_id": interface.id,
            "interface_mac": interface.mac,
            "performed_by": user.id if user else None,
        },
        notified=True,
    )
    return interface
