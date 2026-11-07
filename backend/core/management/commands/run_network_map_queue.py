"""Run only background map saves for local development (no network scans)."""
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from core.network_map_commands import process_next_network_map_command


class Command(BaseCommand):
    help = "Process background network map saves without running scans or integrations."

    def handle(self, *args, **options):
        self.stdout.write("Network map save worker started (no scans).")
        try:
            while True:
                try:
                    close_old_connections()
                    process_next_network_map_command()
                finally:
                    close_old_connections()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Network map save worker stopped.")
