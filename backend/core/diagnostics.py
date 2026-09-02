import platform
import sys
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from .datetime_utils import utc_isoformat
from .models import (
    AdGuardUnmatchedClient,
    AppSettings,
    Device,
    DeviceDNSActivity,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)
from .user_messages import stored_error_message


def _database_size():
    if connection.vendor != "sqlite":
        return None
    database_name = connection.settings_dict.get("NAME")
    if not database_name:
        return None
    try:
        return Path(database_name).stat().st_size
    except OSError:
        return None


def build_diagnostics_report():
    config = AppSettings.load()
    latest_scans = []
    for scan_run in ScanRun.objects.order_by("-started_at")[:10]:
        duration_seconds = None
        if scan_run.finished_at:
            duration_seconds = max(
                0,
                int((scan_run.finished_at - scan_run.started_at).total_seconds()),
            )
        latest_scans.append(
            {
                "status": scan_run.status,
                "started_at": utc_isoformat(scan_run.started_at),
                "duration_seconds": duration_seconds,
                "devices_seen": scan_run.devices_seen,
                "new_devices": scan_run.new_devices,
                "error": stored_error_message("scan", scan_run.error),
            }
        )

    delivery_counts = {
        value: NotificationDelivery.objects.filter(status=value).count()
        for value in NotificationDelivery.Status.values
    }
    scan_counts = {
        value: ScanRun.objects.filter(status=value).count()
        for value in ScanRun.Status.values
    }

    return {
        "report": {
            "format": "languard-diagnostics",
            "format_version": 1,
            "generated_at": utc_isoformat(timezone.now()),
            "privacy": (
                "Credentials, URLs, usernames, device names, IP addresses, MAC addresses, "
                "network ranges, and raw exception text are intentionally omitted."
            ),
        },
        "application": {
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "python": platform.python_version(),
            "django": __import__("django").get_version(),
            "platform": sys.platform,
            "architecture": platform.machine(),
        },
        "database": {
            "engine": connection.vendor,
            "size_bytes": _database_size(),
        },
        "configuration": {
            "scan_interval_minutes": config.scan_interval,
            "time_zone": config.time_zone,
            "activity_retention_days": config.activity_cleanup_retention_days,
            "discord_enabled": config.discord_enabled,
            "discord_configured": bool(config.discord_webhook),
            "telegram_enabled": config.telegram_enabled,
            "telegram_configured": bool(config.telegram_token and config.telegram_user_id),
            "webhook_enabled": config.webhook_enabled,
            "webhook_configured": bool(config.webhook_url),
            "webhook_signature_configured": bool(config.webhook_secret),
            "adguard_enabled": config.adguard_enabled,
            "adguard_configured": bool(
                config.adguard_url
                and (not config.adguard_username or config.adguard_password)
            ),
            "adguard_sync_interval_minutes": config.adguard_sync_interval,
            "adguard_retention_days": config.adguard_retention_days,
            "adguard_last_sync_at": utc_isoformat(config.adguard_last_sync_at),
            "adguard_last_error": stored_error_message(
                "adguard", config.adguard_last_error
            ),
            "speedtest_tracker_enabled": config.speedtest_tracker_enabled,
            "speedtest_tracker_configured": bool(
                config.speedtest_tracker_url
                and config.speedtest_tracker_api_token
            ),
        },
        "counts": {
            "devices": Device.objects.count(),
            "devices_online": Device.objects.filter(online=True).count(),
            "events": NetworkEvent.objects.count(),
            "scan_runs": scan_counts,
            "notification_deliveries": delivery_counts,
            "dns_activity": DeviceDNSActivity.objects.count(),
            "dns_unmatched_clients": AdGuardUnmatchedClient.objects.count(),
        },
        "latest_scans": latest_scans,
    }
