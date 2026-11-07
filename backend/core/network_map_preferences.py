"""Short, bounded preference writes independent of the scanner's application lock."""

import logging
import time

from django.db import OperationalError, connection

from .models import NetworkMapPreference
from .database_writes import sqlite_busy, sqlite_busy_timeout

logger = logging.getLogger(__name__)
RETRY_DELAYS = (0.05, 0.1, 0.2)


def save_network_map_preference(user_id, show_suggestions):
    with sqlite_busy_timeout(250):
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                # A single upsert avoids read-then-write lock upgrades and duplicate user rows.
                NetworkMapPreference.objects.bulk_create(
                    [NetworkMapPreference(user_id=user_id, show_lldp_suggestions=show_suggestions)],
                    update_conflicts=True, update_fields=["show_lldp_suggestions"], unique_fields=["user"],
                )
                return True
            except OperationalError as exc:
                if connection.vendor != "sqlite" or not sqlite_busy(exc):
                    raise
                if attempt < len(RETRY_DELAYS):
                    time.sleep(RETRY_DELAYS[attempt])
        logger.warning("Network Map preference save could not acquire a short SQLite write lock")
        return False
