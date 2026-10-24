import logging
import signal
import threading
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.maintenance import cleanup_all_activity
from core.models import AppSettings, ScanRun
from core.notifications import retry_failed_notifications
from core.scanning.lifecycle import ScanAlreadyRunning
from core.scanning.orchestration import scan
from core.scheduler_runtime import (
    set_next_scheduled_scan,
    start_scheduler_runtime,
    stop_scheduler_runtime,
    touch_scheduler_runtime,
)
from core.integrations.adguard import sync_adguard_query_log
from core.integrations.pihole import sync_pihole
from core.integrations.technitium import sync_technitium
from core.integrations.dhcp import sync_dhcp
from core.versioning import check_for_version_update
from core.integrations.speedtest_tracker import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    check_speedtest_health_change,
)
from core.detailed_port_scans import (
    process_next_detailed_port_scan,
    recover_interrupted_detailed_port_scans,
)
from core.integrations.docker_inventory import sync_enabled_docker_hosts


LOGGER = logging.getLogger(__name__)


def load_scan_schedule(ip_range_override=None, interval_override=None):
    config = AppSettings.load()
    scan_ranges = ip_range_override or config.effective_scan_ranges
    interval = interval_override or config.scan_interval
    return list(scan_ranges), interval


def wait_for_next_scheduled_scan(
    stop_event,
    schedule_anchor,
    ip_range_override=None,
    interval_override=None,
):
    next_scan_at = None
    while not stop_event.is_set():
        close_old_connections()
        try:
            _, interval = load_scan_schedule(ip_range_override, interval_override)
            target = schedule_anchor + timedelta(minutes=interval)
            if target != next_scan_at:
                set_next_scheduled_scan(target)
                next_scan_at = target
        finally:
            close_old_connections()

        remaining_seconds = (target - timezone.now()).total_seconds()
        if remaining_seconds <= 0:
            return True
        if stop_event.wait(
            min(
                remaining_seconds,
                max(1, settings.SCHEDULER_SCHEDULE_POLL_SECONDS),
            )
        ):
            return False
    return False


class Command(BaseCommand):
    help = "Run scheduled network scans."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ip-range",
            action="append",
            default=None,
            help="CIDR range to scan. Repeat for multiple ranges. Defaults to saved app settings.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=None,
            help="Scan interval in minutes. Defaults to saved app settings.",
        )
        parser.add_argument(
            "--run-now",
            action="store_true",
            help="Run one scan immediately before starting the schedule.",
        )
        parser.add_argument(
            "--retry-interval",
            type=int,
            default=settings.NOTIFICATION_RETRY_INTERVAL,
            help="Notification retry interval in minutes.",
        )

    def handle(self, *args, **options):
        ip_range_override = options["ip_range"]
        interval_override = options["interval"]
        retry_interval = options["retry_interval"]
        stop_event = threading.Event()

        def scheduled_scan():
            scan_ranges, _ = load_scan_schedule(ip_range_override, interval_override)
            ranges_label = ", ".join(scan_ranges)
            LOGGER.info("Starting scheduled scan for %s", ranges_label)
            self.stdout.write(f"Starting scheduled scan for {ranges_label}")
            scan(scan_ranges, source=ScanRun.Source.SCHEDULED)
            LOGGER.info("Completed scheduled scan for %s", ranges_label)
            self.stdout.write(self.style.SUCCESS(f"Completed scan for {ranges_label}"))

        def scheduled_notification_retry():
            LOGGER.info("Retrying failed notification deliveries")
            deliveries = retry_failed_notifications()
            if deliveries:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Retried {len(deliveries)} notification deliveries"
                    )
                )

        def scheduled_activity_cleanup():
            retention_days = AppSettings.load().activity_cleanup_retention_days
            LOGGER.info(
                "Cleaning activity records older than %s days",
                retention_days,
            )
            result = cleanup_all_activity(retention_days)
            deleted = result["deleted"]
            self.stdout.write(
                self.style.SUCCESS(
                    "Cleaned activity records older than "
                    f"{retention_days} days: "
                    f"{deleted['events']} events, "
                    f"{deleted['scan_runs']} scan runs, "
                    f"{deleted['notifications']} notifications"
                )
            )

        def run_scheduled_scan():
            close_old_connections()
            try:
                scheduled_scan()
            except ScanAlreadyRunning as exc:
                LOGGER.info("Skipping scheduled network scan: %s", exc)
                self.stdout.write(self.style.WARNING(f"Scheduled scan skipped: {exc}"))
            except Exception:
                LOGGER.exception("Scheduled network scan failed")
                self.stderr.write(self.style.ERROR("Scheduled network scan failed"))
            finally:
                close_old_connections()

        def run_notification_retry():
            close_old_connections()
            try:
                scheduled_notification_retry()
            except Exception:
                LOGGER.exception("Scheduled notification retry failed")
                self.stderr.write(self.style.ERROR("Scheduled notification retry failed"))
            finally:
                close_old_connections()

        def run_activity_cleanup():
            close_old_connections()
            try:
                scheduled_activity_cleanup()
            except Exception:
                LOGGER.exception("Scheduled activity cleanup failed")
                self.stderr.write(self.style.ERROR("Scheduled activity cleanup failed"))
            finally:
                close_old_connections()

        def run_adguard_sync():
            close_old_connections()
            try:
                result = sync_adguard_query_log()
                if result["status"] == "ok":
                    self.stdout.write(
                        self.style.SUCCESS(
                            "AdGuard Home sync completed: "
                            f"{result['matched']} matched queries across "
                            f"{result['domains_updated']} device domains"
                        )
                    )
            except Exception:
                LOGGER.exception("AdGuard Home sync failed")
                self.stderr.write(self.style.ERROR("AdGuard Home sync failed"))
            finally:
                close_old_connections()

        def run_pihole_sync():
            close_old_connections()
            try:
                result = sync_pihole()
                if result["status"] == "ok":
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Pi-hole sync completed: "
                            f"{result['matched']} matched queries across "
                            f"{result['domains_updated']} device domains; "
                            f"{result['leases']} DHCP leases processed"
                        )
                    )
            except Exception:
                LOGGER.exception("Pi-hole sync failed")
                self.stderr.write(self.style.ERROR("Pi-hole sync failed"))
            finally:
                close_old_connections()

        def run_technitium_sync():
            close_old_connections()
            try:
                result = sync_technitium()
                if result["status"] == "ok":
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Technitium sync completed: "
                            f"{result['matched']} matched queries across "
                            f"{result['domains_updated']} device domains; "
                            f"{result['leases']} DHCP leases processed"
                        )
                    )
            except Exception:
                LOGGER.exception("Technitium sync failed")
                self.stderr.write(self.style.ERROR("Technitium sync failed"))
            finally:
                close_old_connections()

        def run_version_update_check():
            close_old_connections()
            try:
                result = check_for_version_update()
                if result["status"] == "notified":
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Sent LanGuard {result['latest_version']} update notification"
                        )
                    )
            except Exception:
                LOGGER.exception("Scheduled version update check failed")
                self.stderr.write(self.style.ERROR("Scheduled version update check failed"))
            finally:
                close_old_connections()

        def dhcp_sync_loop():
            while not stop_event.is_set():
                close_old_connections()
                interval_seconds = 60
                try:
                    config = AppSettings.load()
                    interval_seconds = max(config.dhcp_sync_interval, 1) * 60
                    if config.dhcp_enabled:
                        result = sync_dhcp()
                        LOGGER.info("DHCP source sync completed: %s", result)
                except Exception:
                    LOGGER.exception("DHCP source sync failed")
                finally:
                    close_old_connections()
                if stop_event.wait(interval_seconds):
                    break

        def run_speedtest_health_check():
            close_old_connections()
            try:
                result = check_speedtest_health_change()
                if result["status"] == "notified":
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Sent Speedtest health change notification: "
                            f"{result['health']}"
                        )
                    )
            except Exception:
                LOGGER.exception("Scheduled Speedtest health check failed")
                self.stderr.write(
                    self.style.ERROR("Scheduled Speedtest health check failed")
                )
            finally:
                close_old_connections()

        def run_docker_inventory_sync():
            close_old_connections()
            try:
                results = sync_enabled_docker_hosts()
                completed = sum(result["status"] == "ok" for result in results)
                if completed:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Synced Docker inventory for {completed} host(s)"
                        )
                    )
            except Exception:
                LOGGER.exception("Docker inventory sync failed")
                self.stderr.write(self.style.ERROR("Docker inventory sync failed"))
            finally:
                close_old_connections()

        def retry_loop():
            while not stop_event.wait(retry_interval * 60):
                run_notification_retry()

        def activity_cleanup_loop():
            while not stop_event.wait(24 * 60 * 60):
                run_activity_cleanup()

        def adguard_sync_loop():
            while not stop_event.is_set():
                close_old_connections()
                try:
                    config = AppSettings.load()
                    enabled = config.adguard_enabled
                    interval_seconds = max(config.adguard_sync_interval, 1) * 60
                finally:
                    close_old_connections()
                if enabled:
                    run_adguard_sync()
                if stop_event.wait(interval_seconds):
                    break

        def pihole_sync_loop():
            while not stop_event.is_set():
                close_old_connections()
                try:
                    config = AppSettings.load()
                    enabled = config.pihole_enabled
                    interval_seconds = max(config.pihole_sync_interval, 1) * 60
                finally:
                    close_old_connections()
                if enabled:
                    run_pihole_sync()
                if stop_event.wait(interval_seconds):
                    break

        def technitium_sync_loop():
            while not stop_event.is_set():
                close_old_connections()
                try:
                    config = AppSettings.load()
                    enabled = config.technitium_enabled
                    interval_seconds = max(config.technitium_sync_interval, 1) * 60
                finally:
                    close_old_connections()
                if enabled:
                    run_technitium_sync()
                if stop_event.wait(interval_seconds):
                    break

        def version_update_loop():
            while not stop_event.is_set():
                run_version_update_check()
                close_old_connections()
                try:
                    interval_seconds = max(
                        AppSettings.load().version_check_interval,
                        300,
                    )
                finally:
                    close_old_connections()
                if stop_event.wait(interval_seconds):
                    break

        def speedtest_health_loop():
            while not stop_event.is_set():
                run_speedtest_health_check()
                if stop_event.wait(HEALTH_CHECK_INTERVAL_SECONDS):
                    break

        def detailed_port_scan_loop():
            close_old_connections()
            try:
                recovered = recover_interrupted_detailed_port_scans()
                if recovered:
                    LOGGER.warning("Marked %s interrupted detailed port scans as failed", recovered)
            finally:
                close_old_connections()
            while not stop_event.is_set():
                close_old_connections()
                try:
                    job = process_next_detailed_port_scan()
                    if job:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Detailed port scan {job.id} finished with status {job.status}"
                            )
                        )
                except Exception:
                    LOGGER.exception("Detailed port scan worker failed")
                    self.stderr.write(self.style.ERROR("Detailed port scan worker failed"))
                finally:
                    close_old_connections()
                if stop_event.wait(1):
                    break

        def docker_inventory_loop():
            while not stop_event.is_set():
                run_docker_inventory_sync()
                if stop_event.wait(60):
                    break

        def scheduler_heartbeat_loop():
            while not stop_event.is_set():
                close_old_connections()
                try:
                    touch_scheduler_runtime()
                except Exception:
                    LOGGER.exception("Scheduler heartbeat update failed")
                finally:
                    close_old_connections()
                if stop_event.wait(
                    max(1, settings.SCHEDULER_HEARTBEAT_INTERVAL_SECONDS)
                ):
                    break

        def stop_scheduler(signum, frame):
            self.stdout.write("Stopping scheduler...")
            stop_event.set()

        signal.signal(signal.SIGTERM, stop_scheduler)
        signal.signal(signal.SIGINT, stop_scheduler)

        start_scheduler_runtime()
        heartbeat_thread = threading.Thread(
            target=scheduler_heartbeat_loop,
            daemon=True,
        )
        heartbeat_thread.start()

        retry_thread = threading.Thread(target=retry_loop, daemon=True)
        retry_thread.start()
        activity_cleanup_thread = threading.Thread(target=activity_cleanup_loop, daemon=True)
        activity_cleanup_thread.start()

        schedule_anchor = timezone.now()
        if options["run_now"]:
            set_next_scheduled_scan(None)
            run_scheduled_scan()
            schedule_anchor = timezone.now()

        adguard_sync_thread = threading.Thread(target=adguard_sync_loop, daemon=True)
        adguard_sync_thread.start()
        pihole_sync_thread = threading.Thread(target=pihole_sync_loop, daemon=True)
        pihole_sync_thread.start()
        technitium_sync_thread = threading.Thread(
            target=technitium_sync_loop,
            daemon=True,
        )
        technitium_sync_thread.start()
        dhcp_sync_thread = threading.Thread(target=dhcp_sync_loop, daemon=True)
        dhcp_sync_thread.start()
        version_update_thread = threading.Thread(target=version_update_loop, daemon=True)
        version_update_thread.start()
        speedtest_health_thread = threading.Thread(
            target=speedtest_health_loop,
            daemon=True,
        )
        speedtest_health_thread.start()
        detailed_port_scan_thread = threading.Thread(
            target=detailed_port_scan_loop,
            daemon=True,
        )
        detailed_port_scan_thread.start()
        docker_inventory_thread = threading.Thread(
            target=docker_inventory_loop,
            daemon=True,
        )
        docker_inventory_thread.start()

        if ip_range_override or interval_override:
            scan_ranges, interval = load_scan_schedule(
                ip_range_override,
                interval_override,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "Scheduled network scans "
                    f"{interval} minutes after each scan completes for {', '.join(scan_ranges)}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Scheduled network scans follow the saved ranges and interval"
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduled notification retries every {retry_interval} minutes"
            )
        )
        self.stdout.write(
            self.style.SUCCESS("Scheduled activity cleanup every 24 hours")
        )
        self.stdout.write(
            self.style.SUCCESS("AdGuard Home sync follows the saved integration interval")
        )
        self.stdout.write(
            self.style.SUCCESS("Pi-hole sync follows the saved integration interval")
        )
        self.stdout.write(
            self.style.SUCCESS("Technitium sync follows the saved integration interval")
        )
        self.stdout.write(
            self.style.SUCCESS("LanGuard update checks follow the saved version interval")
        )
        self.stdout.write(
            self.style.SUCCESS("Speedtest health checks run every 5 minutes")
        )
        self.stdout.write(
            self.style.SUCCESS("Detailed device port scans run through the scheduler queue")
        )
        self.stdout.write(
            self.style.SUCCESS("Docker inventory sync follows each host interval")
        )

        try:
            while not stop_event.is_set():
                should_scan = wait_for_next_scheduled_scan(
                    stop_event,
                    schedule_anchor,
                    ip_range_override,
                    interval_override,
                )
                if not should_scan:
                    break
                set_next_scheduled_scan(None)
                run_scheduled_scan()
                schedule_anchor = timezone.now()
        finally:
            stop_event.set()
            heartbeat_thread.join(
                timeout=max(1, settings.SCHEDULER_HEARTBEAT_INTERVAL_SECONDS) + 1
            )
            close_old_connections()
            try:
                stop_scheduler_runtime()
            finally:
                close_old_connections()
