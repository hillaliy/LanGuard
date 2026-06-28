import logging

import requests
from django.conf import settings
from django.utils import timezone

from .models import NetworkEvent, NotificationDelivery


LOGGER = logging.getLogger(__name__)
DISCORD_ALERT_COLOR = 0xE03131


def configured_channels():
    channels = []
    if settings.DISCORD_WEBHOOK:
        channels.append(NotificationDelivery.Channel.DISCORD)
    if settings.TELEGRAM_TOKEN and settings.TELEGRAM_USERID:
        channels.append(NotificationDelivery.Channel.TELEGRAM)
    return channels


def notification_event_types():
    return set(settings.NOTIFICATION_EVENT_TYPES or [])


def notification_event_allowed(event):
    return event.event_type in notification_event_types()


def mark_notification_skipped(event, reason):
    metadata = event.metadata or {}
    event.notified = True
    event.metadata = {
        **metadata,
        "notification_skipped": reason,
    }
    event.save(update_fields=["notified", "metadata"])


def notify_event(event):
    if not settings.NOTIFICATIONS_ENABLED:
        return []

    if not notification_event_allowed(event):
        mark_notification_skipped(event, "event_type_not_enabled")
        return []

    deliveries = []
    for channel in configured_channels():
        delivery = NotificationDelivery.objects.create(
            event=event,
            channel=channel,
        )
        send_delivery(delivery)
        deliveries.append(delivery)

    if deliveries and all(
        delivery.status == NotificationDelivery.Status.SENT for delivery in deliveries
    ):
        event.notified = True
        event.save(update_fields=["notified"])

    return deliveries


def retry_failed_notifications(limit=50, max_attempts=None):
    if not settings.NOTIFICATIONS_ENABLED:
        return []

    max_attempts = max_attempts or settings.NOTIFICATION_MAX_ATTEMPTS
    deliveries = NotificationDelivery.objects.filter(
        status=NotificationDelivery.Status.FAILED,
        attempts__lt=max_attempts,
    ).select_related("event", "event__device")[:limit]

    retried = []
    for delivery in deliveries:
        if not notification_event_allowed(delivery.event):
            delivery.status = NotificationDelivery.Status.SKIPPED
            delivery.error = "Event type is not enabled for external notifications."
            delivery.save(update_fields=["status", "error"])
            mark_notification_skipped(delivery.event, "event_type_not_enabled")
            continue
        send_delivery(delivery)
        retried.append(delivery)

    events = {delivery.event for delivery in retried}
    for event in events:
        if event.notifications.exists() and not event.notifications.exclude(
            status=NotificationDelivery.Status.SENT
        ).exists():
            event.notified = True
            event.save(update_fields=["notified"])

    return retried


def send_delivery(delivery):
    delivery.attempts += 1
    try:
        if delivery.channel == NotificationDelivery.Channel.DISCORD:
            send_discord(delivery.event)
        elif delivery.channel == NotificationDelivery.Channel.TELEGRAM:
            send_telegram(delivery.event)
        else:
            delivery.status = NotificationDelivery.Status.SKIPPED
            delivery.error = f"Unsupported channel: {delivery.channel}"
            delivery.save(update_fields=["attempts", "status", "error"])
            return
    except requests.RequestException as exc:
        LOGGER.warning("Notification delivery failed: %s", exc)
        delivery.status = NotificationDelivery.Status.FAILED
        delivery.error = str(exc)
        delivery.save(update_fields=["attempts", "status", "error"])
        return

    delivery.status = NotificationDelivery.Status.SENT
    delivery.error = ""
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["attempts", "status", "error", "sent_at"])


def send_discord(event):
    response = requests.post(
        settings.DISCORD_WEBHOOK,
        json=format_discord_payload(event),
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def send_telegram(event):
    response = requests.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": settings.TELEGRAM_USERID,
            "text": format_event_message(event),
            "disable_web_page_preview": True,
        },
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def format_event_message(event):
    device = event.device
    lines = [
        f"LanGuard: {event.get_event_type_display()}",
        event.message,
        f"Device: {device.name}",
        f"IP: {device.ip}",
        f"MAC: {device.mac}",
    ]
    if device.vendor:
        lines.append(f"Vendor: {device.vendor}")
    return "\n".join(lines)


def format_discord_payload(event):
    device = event.device
    icon_url = settings.DISCORD_ICON_URL
    fields = [
        {"name": "Device", "value": device.name or "-", "inline": True},
        {"name": "IP", "value": device.ip or "-", "inline": True},
        {"name": "MAC", "value": device.mac or "-", "inline": True},
    ]
    if device.vendor:
        fields.append({"name": "Vendor", "value": device.vendor, "inline": False})

    embed = {
        "title": f"LanGuard: {event.get_event_type_display()}",
        "description": event.message,
        "color": DISCORD_ALERT_COLOR,
        "fields": fields,
        "timestamp": event.created_at.isoformat(),
        "footer": {"text": "LanGuard"},
    }
    if icon_url:
        embed["author"] = {
            "name": "LanGuard",
            "icon_url": icon_url,
        }
        embed["thumbnail"] = {"url": icon_url}

    payload = {
        "username": "LanGuard",
        "embeds": [embed],
    }
    if icon_url:
        payload["avatar_url"] = icon_url
    return payload
