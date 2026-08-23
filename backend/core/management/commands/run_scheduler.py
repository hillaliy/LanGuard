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


LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run scheduled network scans."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ip-range",
            default=None,
            help="CIDR range to scan. Defaults to saved app settings.",
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
        app_config = AppSettings.load()
        ip_range = options["ip_range"] or app_config.ip_range
        interval = options["interval"] or app_config.scan_interval
        retry_interval = options["retry_interval"]
        stop_event = threading.Event()

        def scheduled_scan():
            LOGGER.info("Starting scheduled scan for %s", ip_range)
            self.stdout.write(f"Starting scheduled scan for {ip_range}")
            scan(ip_range)
            LOGGER.info("Completed scheduled scan for %s", ip_range)
            self.stdout.write(self.style.SUCCESS(f"Completed scan for {ip_range}"))

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
                LOGGER.exception("Scheduled scan failed for %s", ip_range)
                self.stderr.write(self.style.ERROR(f"Scheduled scan failed for {ip_range}"))
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

        def retry_loop():
            while not stop_event.wait(retry_interval * 60):
                run_notification_retry()

        def activity_cleanup_loop():
            while not stop_event.wait(24 * 60 * 60):
                run_activity_cleanup()

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduled network scans {interval} minutes after each scan completes for {ip_range}"
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

        while not stop_event.wait(interval * 60):
            run_scheduled_scan()
