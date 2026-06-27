import time

from django.conf import settings
from django.core.management.base import BaseCommand

from core.scan import scan


class Command(BaseCommand):
    help = "Scan the configured network range and update discovered devices."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ip-range",
            default=settings.IP_RANGE,
            help="CIDR range to scan. Defaults to IP_RANGE from settings.",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Keep scanning every INTERVAL minutes.",
        )

    def handle(self, *args, **options):
        ip_range = options["ip_range"]

        while True:
            self.stdout.write(f"Scanning {ip_range}...")
            scan(ip_range)
            self.stdout.write(self.style.SUCCESS(f"Scan completed for {ip_range}"))

            if not options["loop"]:
                break

            time.sleep(settings.INTERVAL * 60)
