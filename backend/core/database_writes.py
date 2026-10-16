import threading
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


_PROCESS_WRITE_LOCK = threading.Lock()


def _sqlite_lock_path():
    database = settings.DATABASES["default"]
    if database.get("ENGINE") != "django.db.backends.sqlite3":
        return None

    database_name = str(database.get("NAME") or "")
    if (
        not database_name
        or database_name == ":memory:"
        or database_name.startswith("file:")
    ):
        return None
    return Path(f"{database_name}.write.lock")


@contextmanager
def serialized_database_write():
    with _PROCESS_WRITE_LOCK:
        lock_path = _sqlite_lock_path()
        if lock_path is None or fcntl is None:
            yield
            return

        # The database volume is shared by the web and scheduler containers.
        with lock_path.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
