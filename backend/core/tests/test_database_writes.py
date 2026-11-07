import threading
import time
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase

from ..database_writes import DatabaseWriteBusy, _PROCESS_WRITE_LOCK, fcntl, serialized_database_write


class SerializedDatabaseWriteTests(SimpleTestCase):
    def test_bounded_thread_lock_wait_does_not_enter_write_and_releases_cleanly(self):
        _PROCESS_WRITE_LOCK.acquire()
        try:
            with self.assertRaises(DatabaseWriteBusy):
                with serialized_database_write(timeout=0.01):
                    self.fail("Busy write must not run")
        finally:
            _PROCESS_WRITE_LOCK.release()
        with serialized_database_write(timeout=0.1):
            pass

    @skipUnless(fcntl, "Interprocess locking requires fcntl")
    def test_bounded_file_lock_wait_releases_thread_lock_and_allows_later_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "test.write.lock"
            with lock_path.open("a+") as held, patch("core.database_writes._sqlite_lock_path", return_value=lock_path):
                fcntl.flock(held.fileno(), fcntl.LOCK_EX)
                try:
                    with self.assertRaises(DatabaseWriteBusy):
                        with serialized_database_write(timeout=0.02):
                            self.fail("A scanner-held file lock must not be bypassed")
                    self.assertFalse(_PROCESS_WRITE_LOCK.locked())
                finally:
                    fcntl.flock(held.fileno(), fcntl.LOCK_UN)
                with serialized_database_write(timeout=0.1):
                    pass

    def test_lock_is_released_after_an_exception(self):
        with self.assertRaisesRegex(RuntimeError, "failed writer"):
            with serialized_database_write():
                raise RuntimeError("failed writer")

        with serialized_database_write():
            acquired_again = True

        self.assertTrue(acquired_again)

    def test_concurrent_writers_run_one_at_a_time(self):
        first_started = threading.Event()
        release_first = threading.Event()
        second_attempting = threading.Event()
        second_started = threading.Event()
        execution_order = []

        def first_writer():
            with serialized_database_write():
                execution_order.append("first-start")
                first_started.set()
                release_first.wait(timeout=2)
                execution_order.append("first-end")

        def second_writer():
            first_started.wait(timeout=2)
            second_attempting.set()
            with serialized_database_write():
                execution_order.append("second-start")
                second_started.set()

        first_thread = threading.Thread(target=first_writer)
        second_thread = threading.Thread(target=second_writer)
        first_thread.start()
        second_thread.start()

        self.assertTrue(first_started.wait(timeout=2))
        self.assertTrue(second_attempting.wait(timeout=2))
        time.sleep(0.05)
        self.assertFalse(second_started.is_set())

        release_first.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(
            execution_order,
            ["first-start", "first-end", "second-start"],
        )
