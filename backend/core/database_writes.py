import threading
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.db import connection

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


_PROCESS_WRITE_LOCK = threading.Lock()


class DatabaseWriteBusy(Exception):
    pass


@contextmanager
def sqlite_busy_timeout(milliseconds):
    if connection.vendor != "sqlite":
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout")
        previous = cursor.fetchone()[0]
        cursor.execute(f"PRAGMA busy_timeout = {int(milliseconds)}")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA busy_timeout = {int(previous)}")


def sqlite_busy(error):
    code = getattr(error.__cause__, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xff in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return str(error).lower() in ("database is locked", "database table is locked", "database schema is locked")


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
def serialized_database_write(*, timeout=None):
    deadline = None if timeout is None else time.monotonic() + timeout
    acquired = _PROCESS_WRITE_LOCK.acquire() if deadline is None else _PROCESS_WRITE_LOCK.acquire(timeout=max(0, timeout))
    if not acquired:
        raise DatabaseWriteBusy
    try:
        lock_path = _sqlite_lock_path()
        if lock_path is None or fcntl is None:
            yield
            return

        # The database volume is shared by the web and scheduler containers.
        with lock_path.open("a+") as lock_file:
            if deadline is None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            else:
                while True:
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise DatabaseWriteBusy from None
                        time.sleep(min(0.05, remaining))
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        _PROCESS_WRITE_LOCK.release()
