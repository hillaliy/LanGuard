from django.core.management.base import BaseCommand

from core.models import AppSettings
from core.scan import scan


class Command(BaseCommand):
    help = "Scan the configured network range and update discovered devices."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ip-range",
            action="append",
            default=None,
            help="CIDR range to scan. Repeat for multiple ranges. Defaults to saved app settings.",
        )
    def handle(self, *args, **options):
        scan_ranges = options["ip_range"] or AppSettings.load().effective_scan_ranges
        ranges_label = ", ".join(scan_ranges)

        self.stdout.write(f"Scanning {ranges_label}...")
        scan(scan_ranges)
        self.stdout.write(self.style.SUCCESS(f"Scan completed for {ranges_label}"))
