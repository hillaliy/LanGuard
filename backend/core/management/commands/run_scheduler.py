import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand

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

        def run_scheduled_scan():
            try:
                scheduled_scan()
            except Exception:
                LOGGER.exception("Scheduled scan failed for %s", ip_range)
                self.stderr.write(self.style.ERROR(f"Scheduled scan failed for {ip_range}"))

        def run_notification_retry():
            try:
                scheduled_notification_retry()
            except Exception:
                LOGGER.exception("Scheduled notification retry failed")
                self.stderr.write(self.style.ERROR("Scheduled notification retry failed"))

        def retry_loop():
            while not stop_event.wait(retry_interval * 60):
                run_notification_retry()

        def stop_scheduler(signum, frame):
            self.stdout.write("Stopping scheduler...")
            stop_event.set()

        signal.signal(signal.SIGTERM, stop_scheduler)
        signal.signal(signal.SIGINT, stop_scheduler)

        retry_thread = threading.Thread(target=retry_loop, daemon=True)
        retry_thread.start()

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

        while not stop_event.wait(interval * 60):
            run_scheduled_scan()
