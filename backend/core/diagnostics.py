import platform
import sys
from datetime import timedelta
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
    DeviceIPAddressAssignment,
    DetailedPortScan,
    DockerHost,
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


def _database_runtime():
    if connection.vendor != "sqlite":
        return {}
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout")
        busy_timeout_ms = cursor.fetchone()[0]
    return {
        "journal_mode": journal_mode,
        "busy_timeout_ms": busy_timeout_ms,
    }


def build_diagnostics_report():
    config = AppSettings.load()
    generated_at = timezone.now()
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
                "source": scan_run.source,
                "started_at": utc_isoformat(scan_run.started_at),
                "finished_at": utc_isoformat(scan_run.finished_at),
                "duration_seconds": duration_seconds,
                "devices_seen": scan_run.devices_seen,
                "new_devices": scan_run.new_devices,
                "error": stored_error_message("scan", scan_run.error),
                "failure_code": scan_run.failure_code,
                "failure_type": scan_run.failure_type,
                "failure_stage": scan_run.failure_stage,
                "failure_fingerprint": scan_run.failure_fingerprint,
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
    recent_scan_counts = {
        value: ScanRun.objects.filter(
            status=value,
            started_at__gte=generated_at - timedelta(hours=24),
        ).count()
        for value in ScanRun.Status.values
    }
    detailed_scan_counts = {
        value: DetailedPortScan.objects.filter(status=value).count()
        for value in DetailedPortScan.Status.values
    }
    docker_hosts = DockerHost.objects.filter(enabled=True)

    return {
        "report": {
            "format": "languard-diagnostics",
            "format_version": 2,
            "generated_at": utc_isoformat(generated_at),
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
            **_database_runtime(),
        },
        "configuration": {
            "scan_interval_minutes": config.scan_interval,
            "scan_network_count": len(config.effective_scan_ranges),
            "time_zone": config.time_zone,
            "activity_retention_days": config.activity_cleanup_retention_days,
            "discord_enabled": config.discord_enabled,
            "discord_configured": bool(config.discord_webhook),
            "telegram_enabled": config.telegram_enabled,
            "telegram_configured": bool(config.telegram_token and config.telegram_user_id),
            "ntfy_enabled": config.ntfy_enabled,
            "ntfy_configured": bool(config.ntfy_server_url and config.ntfy_topic),
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
            "pihole_enabled": config.pihole_enabled,
            "pihole_configured": bool(config.pihole_url and config.pihole_password),
            "pihole_sync_interval_minutes": config.pihole_sync_interval,
            "pihole_retention_days": config.pihole_retention_days,
            "pihole_last_sync_at": utc_isoformat(config.pihole_last_sync_at),
            "pihole_last_error": stored_error_message(
                "pihole", config.pihole_last_error
            ),
            "speedtest_tracker_enabled": config.speedtest_tracker_enabled,
            "notify_speedtest_changes": config.notify_speedtest_changes,
            "speedtest_tracker_configured": bool(
                config.speedtest_tracker_url
                and config.speedtest_tracker_api_token
            ),
            "docker_inventory_enabled_hosts": docker_hosts.count(),
            "docker_inventory_sync_intervals_minutes": sorted(
                set(docker_hosts.values_list("sync_interval", flat=True))
            ),
        },
        "counts": {
            "devices": Device.objects.count(),
            "devices_online": Device.objects.filter(online=True).count(),
            "events": NetworkEvent.objects.count(),
            "scan_runs": scan_counts,
            "scan_runs_last_24_hours": recent_scan_counts,
            "detailed_port_scans": detailed_scan_counts,
            "notification_deliveries": delivery_counts,
            "dns_activity": DeviceDNSActivity.objects.count(),
            "dns_unmatched_clients": AdGuardUnmatchedClient.objects.count(),
            "device_ip_assignments": DeviceIPAddressAssignment.objects.count(),
        },
        "latest_scans": latest_scans,
    }
