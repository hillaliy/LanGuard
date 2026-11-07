import sqlite3
import threading
import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from ..database_writes import _PROCESS_WRITE_LOCK
from ..models import Device, NetworkLink, NetworkMapPreference
from ..network_map_preferences import save_network_map_preference


class PreferenceScanLockTests(TestCase):
    def test_preference_saves_while_scan_application_lock_is_held(self):
        user = User.objects.create_user("scan-lock-viewer")
        client = APIClient()
        client.force_authenticate(user)
        self.assertTrue(_PROCESS_WRITE_LOCK.acquire(timeout=1))
        rescue = threading.Timer(2, _PROCESS_WRITE_LOCK.release)
        rescue.start()
        try:
            start = time.monotonic()
            response = client.put("/api/v1/network-map/preferences/", {"show_lldp_suggestions": True}, format="json")
            self.assertLess(time.monotonic() - start, 1)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(NetworkMapPreference.objects.get(user=user).show_lldp_suggestions)
        finally:
            rescue.cancel()
            rescue.join()
            if _PROCESS_WRITE_LOCK.locked():
                _PROCESS_WRITE_LOCK.release()

    def test_focused_get_is_personal_and_does_not_create_rows(self):
        first = User.objects.create_user("pref-first")
        second = User.objects.create_user("pref-second")
        NetworkMapPreference.objects.create(user=first, show_lldp_suggestions=True)
        client = APIClient()
        self.assertEqual(client.get("/api/v1/network-map/preferences/").status_code, 401)
        for user, expected in ((first, True), (second, False)):
            client.force_authenticate(user)
            response = client.get("/api/v1/network-map/preferences/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["data"], {"show_lldp_suggestions": expected})
        self.assertEqual(NetworkMapPreference.objects.count(), 1)

    def test_unrelated_database_errors_are_not_treated_as_contention(self):
        with patch("core.network_map_preferences.NetworkMapPreference.objects.bulk_create", side_effect=OperationalError("no such table")):
            with self.assertRaisesRegex(OperationalError, "no such table"):
                save_network_map_preference(1, True)


class PreferenceSQLiteContentionTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "sqlite":
            self.skipTest("SQLite-specific contention checks")
        self.user = User.objects.create_user("sqlite-pref-viewer")
        NetworkMapPreference.objects.create(user=self.user, show_lldp_suggestions=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        database = str(connection.settings_dict["NAME"])
        self.blocker = sqlite3.connect(database, uri=database.startswith("file:"), isolation_level=None)
        self.addCleanup(self.blocker.close)
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout")
            self.original_timeout = cursor.fetchone()[0]

    def hold_write(self):
        self.blocker.execute("BEGIN IMMEDIATE")
        self.blocker.execute("UPDATE core_networkmappreference SET show_lldp_suggestions = show_lldp_suggestions")

    def assert_timeout_restored(self):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout")
            self.assertEqual(cursor.fetchone()[0], self.original_timeout)

    def test_busy_database_returns_bounded_503_preserves_state_and_can_retry(self):
        self.hold_write()
        try:
            start = time.monotonic()
            response = self.client.put("/api/v1/network-map/preferences/", {"show_lldp_suggestions": False}, format="json")
            self.assertLess(time.monotonic() - start, 3)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response["Retry-After"], "1")
            self.assert_timeout_restored()
        finally:
            self.blocker.rollback()
        self.assertTrue(NetworkMapPreference.objects.get(user=self.user).show_lldp_suggestions)
        response = self.client.put("/api/v1/network-map/preferences/", {"show_lldp_suggestions": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NetworkMapPreference.objects.get(user=self.user).show_lldp_suggestions)
        self.assert_timeout_restored()

    def test_transient_contention_retries_after_lock_is_released(self):
        self.hold_write()
        try:
            with patch("core.network_map_preferences.time.sleep", side_effect=lambda _: self.blocker.rollback()) as pause:
                response = self.client.put("/api/v1/network-map/preferences/", {"show_lldp_suggestions": False}, format="json")
            self.assertEqual(response.status_code, 200)
            pause.assert_called_once()
        finally:
            self.blocker.rollback()
        self.assertFalse(NetworkMapPreference.objects.get(user=self.user).show_lldp_suggestions)
        self.assertEqual(NetworkMapPreference.objects.count(), 1)
        self.assert_timeout_restored()

    def test_bulk_database_busy_rolls_back_the_entire_batch(self):
        from ..views.network_map import save_link

        devices = [Device.objects.create(mac=f"aa:bb:cc:dd:ee:0{index}", ip=f"192.168.1.{index}") for index in range(1, 4)]
        calls = 0

        def busy_after_first(serializer):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OperationalError("database is locked")
            return save_link(serializer)

        with patch("core.views.network_map.save_link", side_effect=busy_after_first):
            response = self.client.post("/api/v1/network-map/links/bulk/", {"connections": [
                {"source": devices[0].pk, "target": device.pk} for device in devices[1:]
            ]}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(NetworkLink.objects.exists())
        self.assert_timeout_restored()
