import logging
import signal
import threading

from django.conf import settings
from django.db import close_old_connections
from django.core.management.base import BaseCommand

from core.maintenance import cleanup_all_activity
from core.models import AppSettings
from core.notifications import retry_failed_notifications
from core.scan import scan
from core.adguard import sync_adguard_query_log


LOGGER = logging.getLogger(__name__)


def load_scan_schedule(ip_range_override=None, interval_override=None):
    config = AppSettings.load()
    scan_ranges = ip_range_override or config.effective_scan_ranges
    interval = interval_override or config.scan_interval
    return list(scan_ranges), interval


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
            scan(scan_ranges)
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

        def stop_scheduler(signum, frame):
            self.stdout.write("Stopping scheduler...")
            stop_event.set()

        signal.signal(signal.SIGTERM, stop_scheduler)
        signal.signal(signal.SIGINT, stop_scheduler)

        retry_thread = threading.Thread(target=retry_loop, daemon=True)
        retry_thread.start()
        activity_cleanup_thread = threading.Thread(target=activity_cleanup_loop, daemon=True)
        activity_cleanup_thread.start()

        if options["run_now"]:
            run_scheduled_scan()

        adguard_sync_thread = threading.Thread(target=adguard_sync_loop, daemon=True)
        adguard_sync_thread.start()

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

        while not stop_event.is_set():
            _, interval = load_scan_schedule(ip_range_override, interval_override)
            close_old_connections()
            if stop_event.wait(interval * 60):
                break
            run_scheduled_scan()
