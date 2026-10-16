import threading
import time

from django.test import SimpleTestCase

from ..database_writes import serialized_database_write


class SerializedDatabaseWriteTests(SimpleTestCase):
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
