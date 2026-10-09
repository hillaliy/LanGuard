from ..device_merging import primary_device
from ..models import Device, NetworkEvent
from ..notifications import notify_event


def create_event(event_type, device, message, scan_run=None, device_port=None, metadata=None):
    metadata = metadata or {}
    presence_events = {
        NetworkEvent.EventType.DEVICE_ONLINE,
        NetworkEvent.EventType.DEVICE_OFFLINE,
    }
    source_device = device
    authoritative_device = primary_device(device) if device else None
    skip_presence_notification = False
    if device and event_type in presence_events:
        other_interface_online = Device.objects.filter(
            merged_into=authoritative_device,
            online=True,
        ).exclude(id=device.id).exists()
        if authoritative_device.id != device.id:
            other_interface_online = other_interface_online or authoritative_device.online
        skip_presence_notification = other_interface_online
        metadata = {
            **metadata,
            "interface_device_id": source_device.id,
            "interface_mac": source_device.mac,
            "interface_ip": source_device.ip,
        }
        if not skip_presence_notification:
            device = authoritative_device
            verb = "came online" if event_type == NetworkEvent.EventType.DEVICE_ONLINE else "went offline"
            message = f"{authoritative_device.name} {verb}"
    event = NetworkEvent.objects.create(
        scan_run=scan_run,
        device=device,
        device_port=device_port,
        event_type=event_type,
        message=message,
        metadata=metadata,
    )
    if skip_presence_notification:
        event.notified = True
        event.metadata = {
            **metadata,
            "notification_skipped": "other_interface_online",
        }
        event.save(update_fields=["notified", "metadata"])
    elif authoritative_device and authoritative_device.known and event_type not in presence_events:
        event.notified = True
        event.metadata = {
            **metadata,
            "notification_skipped": "known_device",
        }
        event.save(update_fields=["notified", "metadata"])
    else:
        notify_event(event)
    return event
