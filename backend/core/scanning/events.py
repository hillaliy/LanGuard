from ..models import NetworkEvent
from ..notifications import notify_event


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
    presence_events = {
        NetworkEvent.EventType.DEVICE_ONLINE,
        NetworkEvent.EventType.DEVICE_OFFLINE,
    }
    if device and device.known and event_type not in presence_events:
        event.notified = True
        event.metadata = {
            **metadata,
            "notification_skipped": "known_device",
        }
        event.save(update_fields=["notified", "metadata"])
    else:
        notify_event(event)
    return event
