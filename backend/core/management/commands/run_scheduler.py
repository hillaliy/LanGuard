import logging
import signal

from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.core.management.base import BaseCommand

from core.notifications import retry_failed_notifications
from core.scan import scan


LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run scheduled network scans."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ip-range",
            default=settings.IP_RANGE,
            help="CIDR range to scan. Defaults to IP_RANGE from settings.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=settings.INTERVAL,
            help="Scan interval in minutes. Defaults to INTERVAL from settings.",
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
        ip_range = options["ip_range"]
        interval = options["interval"]
        retry_interval = options["retry_interval"]
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)

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

        scheduler.add_job(
            scheduled_scan,
            "interval",
            minutes=interval,
            id="network_scan",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        scheduler.add_job(
            scheduled_notification_retry,
            "interval",
            minutes=retry_interval,
            id="notification_retry",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        def stop_scheduler(signum, frame):
            self.stdout.write("Stopping scheduler...")
            scheduler.shutdown(wait=False)

        signal.signal(signal.SIGTERM, stop_scheduler)
        signal.signal(signal.SIGINT, stop_scheduler)

        if options["run_now"]:
            scheduled_scan()

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduled network scans every {interval} minutes for {ip_range}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduled notification retries every {retry_interval} minutes"
            )
        )
        scheduler.start()
