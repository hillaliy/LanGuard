from django.conf import settings
from django.core.management.base import BaseCommand

from core.notifications import retry_failed_notifications


class Command(BaseCommand):
    help = "Retry failed notification deliveries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of failed deliveries to retry.",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=settings.NOTIFICATION_MAX_ATTEMPTS,
            help="Maximum delivery attempts before a failed notification is ignored.",
        )

    def handle(self, *args, **options):
        deliveries = retry_failed_notifications(
            limit=options["limit"],
            max_attempts=options["max_attempts"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Retried {len(deliveries)} notification deliveries.")
        )
