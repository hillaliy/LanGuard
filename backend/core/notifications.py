import logging
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from django.conf import settings
from django.utils import timezone

from .datetime_utils import utc_isoformat
from .models import (
    AppSettings,
    NetworkEvent,
    NotificationDelivery,
    QUIET_HOURS_DAY_KEYS,
)
from .user_messages import external_service_error


LOGGER = logging.getLogger(__name__)
DISCORD_ALERT_COLOR = 0xE03131
DISCORD_TEST_COLOR = 0x228BE6
TEST_NOTIFICATION_MESSAGE = (
    "This is a test notification from LanGuard. Your notification channel is working."
)
def configured_channels(app_config=None):
    app_config = app_config or AppSettings.load()
    channels = []
    if app_config.discord_enabled and app_config.discord_webhook:
        channels.append(NotificationDelivery.Channel.DISCORD)
    if app_config.telegram_enabled and app_config.telegram_token and app_config.telegram_user_id:
        channels.append(NotificationDelivery.Channel.TELEGRAM)
    if app_config.webhook_enabled and app_config.webhook_url:
        channels.append(NotificationDelivery.Channel.WEBHOOK)
    return channels


def notification_event_types():
    return set(settings.NOTIFICATION_EVENT_TYPES or [])


def notification_event_allowed(event):
    app_config = AppSettings.load()
    if event.event_type == NetworkEvent.EventType.NEW_DEVICE:
        return app_config.notify_new_devices
    if event.event_type == NetworkEvent.EventType.DEVICE_ONLINE:
        return app_config.notify_device_online
    if event.event_type == NetworkEvent.EventType.DEVICE_OFFLINE:
        return app_config.notify_device_offline
    if event.event_type in {
        NetworkEvent.EventType.PORT_OPENED,
        NetworkEvent.EventType.PORT_CLOSED,
    }:
        return app_config.notify_port_changes
    return event.event_type in notification_event_types()


def quiet_hours_active(app_config, now=None):
    if not app_config.notification_quiet_hours_enabled:
        return False

    now = now or timezone.now()
    try:
        app_timezone = ZoneInfo(app_config.time_zone)
    except ZoneInfoNotFoundError:
        app_timezone = timezone.get_current_timezone()

    if timezone.is_naive(now):
        now = timezone.make_aware(now, app_timezone)
    local_now = timezone.localtime(now, app_timezone)
    local_time = local_now.time()
    start = time.fromisoformat(app_config.notification_quiet_hours_start)
    end = time.fromisoformat(app_config.notification_quiet_hours_end)
    selected_days = app_config.notification_quiet_hours_days

    quiet_period_weekday = local_now.weekday()
    if start > end and local_time < end:
        quiet_period_weekday = (quiet_period_weekday - 1) % 7
    if QUIET_HOURS_DAY_KEYS[quiet_period_weekday] not in selected_days:
        return False

    if start == end:
        return True
    if start < end:
        return start <= local_time < end
    return local_time >= start or local_time < end


def mark_notification_skipped(event, reason):
    metadata = event.metadata or {}
    event.notified = True
    event.metadata = {
        **metadata,
        "notification_skipped": reason,
    }
    event.save(update_fields=["notified", "metadata"])


def notify_event(event):
    app_config = AppSettings.load()

    if not notification_event_allowed(event):
        mark_notification_skipped(event, "event_type_not_enabled")
        return []

    if quiet_hours_active(app_config):
        mark_notification_skipped(event, "quiet_hours")
        return []

    deliveries = []
    for channel in configured_channels(app_config):
        delivery = NotificationDelivery.objects.create(
            event=event,
            channel=channel,
        )
        send_delivery(delivery, app_config=app_config)
        deliveries.append(delivery)

    if deliveries and all(
        delivery.status == NotificationDelivery.Status.SENT for delivery in deliveries
    ):
        event.notified = True
        event.save(update_fields=["notified"])

    return deliveries


def retry_failed_notifications(limit=50, max_attempts=None):
    app_config = AppSettings.load()

    max_attempts = max_attempts or settings.NOTIFICATION_MAX_ATTEMPTS
    deliveries = NotificationDelivery.objects.filter(
        status=NotificationDelivery.Status.FAILED,
        attempts__lt=max_attempts,
        event__isnull=False,
    ).select_related("event", "event__device")[:limit]

    retried = []
    for delivery in deliveries:
        if not notification_event_allowed(delivery.event):
            delivery.status = NotificationDelivery.Status.SKIPPED
            delivery.error = "Event type is not enabled for external notifications."
            delivery.save(update_fields=["status", "error"])
            mark_notification_skipped(delivery.event, "event_type_not_enabled")
            continue
        send_delivery(delivery, app_config=app_config)
        retried.append(delivery)

    events = {delivery.event for delivery in retried}
    for event in events:
        if event.notifications.exists() and not event.notifications.exclude(
            status=NotificationDelivery.Status.SENT
        ).exists():
            event.notified = True
            event.save(update_fields=["notified"])

    return retried


def send_delivery(delivery, app_config=None):
    app_config = app_config or AppSettings.load()
    delivery.attempts += 1
    try:
        if delivery.channel == NotificationDelivery.Channel.DISCORD:
            send_discord(delivery.event, app_config)
        elif delivery.channel == NotificationDelivery.Channel.TELEGRAM:
            send_telegram(delivery.event, app_config)
        elif delivery.channel == NotificationDelivery.Channel.WEBHOOK:
            send_webhook(delivery.event, app_config)
        else:
            delivery.status = NotificationDelivery.Status.SKIPPED
            delivery.error = f"Unsupported channel: {delivery.channel}"
            delivery.save(update_fields=["attempts", "status", "error"])
            return
    except requests.RequestException as exc:
        response_status = getattr(getattr(exc, "response", None), "status_code", None)
        LOGGER.warning(
            "Notification delivery failed: channel=%s status=%s",
            delivery.channel,
            response_status or "unavailable",
        )
        delivery.status = NotificationDelivery.Status.FAILED
        delivery.error = external_service_error(delivery.get_channel_display(), exc)
        delivery.save(update_fields=["attempts", "status", "error"])
        return

    delivery.status = NotificationDelivery.Status.SENT
    delivery.error = ""
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["attempts", "status", "error", "sent_at"])


def send_discord(event, app_config):
    response = requests.post(
        app_config.discord_webhook,
        json=format_discord_payload(event),
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def send_telegram(event, app_config):
    response = requests.post(
        f"https://api.telegram.org/bot{app_config.telegram_token}/sendMessage",
        json={
            "chat_id": app_config.telegram_user_id,
            "text": format_event_message(event),
            "disable_web_page_preview": True,
        },
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def send_webhook(event, app_config):
    response = requests.post(
        app_config.webhook_url,
        json=format_webhook_payload(event),
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def send_discord_test(webhook):
    response = requests.post(
        webhook,
        json=format_discord_test_payload(),
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def send_telegram_test(token, user_id):
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": user_id,
            "text": f"LanGuard: Test notification\n{TEST_NOTIFICATION_MESSAGE}",
            "disable_web_page_preview": True,
        },
        timeout=settings.NOTIFICATION_TIMEOUT,
    )
    response.raise_for_status()


def send_webhook_test(webhook_url):
    response = requests.post(
        webhook_url,
        json={
            "source": "languard",
            "kind": "test",
            "message": TEST_NOTIFICATION_MESSAGE,
            "created_at": utc_isoformat(timezone.now()),
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


def format_webhook_payload(event):
    device = event.device
    return {
        "source": "languard",
        "kind": "network_event",
        "event": {
            "id": event.id,
            "type": event.event_type,
            "label": event.get_event_type_display(),
            "message": event.message,
            "created_at": utc_isoformat(event.created_at),
            "metadata": event.metadata or {},
        },
        "device": {
            "id": device.id,
            "name": device.name,
            "hostname": device.hostname,
            "ip": device.ip,
            "mac": device.mac,
            "vendor": device.vendor,
            "role": device.role,
            "room": device.room,
            "known": device.known,
            "online": device.online,
            "status": device.status,
        },
        "scan_run_id": event.scan_run_id,
    }


def format_discord_test_payload():
    icon_url = settings.DISCORD_ICON_URL
    embed = {
        "title": "LanGuard: Test notification",
        "description": TEST_NOTIFICATION_MESSAGE,
        "color": DISCORD_TEST_COLOR,
        "timestamp": utc_isoformat(timezone.now()),
        "footer": {"text": "LanGuard"},
    }
    if icon_url:
        embed["author"] = {"name": "LanGuard", "icon_url": icon_url}
        embed["thumbnail"] = {"url": icon_url}

    payload = {"username": "LanGuard", "embeds": [embed]}
    if icon_url:
        payload["avatar_url"] = icon_url
    return payload


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
        "timestamp": utc_isoformat(event.created_at),
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
