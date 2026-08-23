from django.apps import AppConfig
from django.db.backends.signals import connection_created


def configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return

    timeout_seconds = connection.settings_dict.get("OPTIONS", {}).get("timeout", 30)
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA busy_timeout = {int(timeout_seconds) * 1000}")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        connection_created.connect(
            configure_sqlite_connection,
            dispatch_uid="core.configure_sqlite_connection",
        )
