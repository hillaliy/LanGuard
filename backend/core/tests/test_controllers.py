from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..integrations.controllers import ControllerBusy, sync_connection
from ..integrations.unifi import ControllerError, UniFiProvider, normalize_url
from ..models import ControllerConnection, ControllerDeviceLink, Device
from .test_asuswrt import http_response

SITE = "10000000-0000-4000-8000-000000000001"
EXTERNAL = "20000000-0000-4000-8000-000000000001"
URL = "https://controller.example"
KEY = "private-unifi-key"
MAC = "02:00:00:00:00:10"
IP = "192.168.1.20"
BASE = "/api/v1/integrations/controllers/unifi/"


def page(rows, offset=0, total=None):
    return http_response({"data": rows, "offset": offset, "count": len(rows),
                          "totalCount": len(rows) if total is None else total})


class UniFiProviderTests(SimpleTestCase):
    def test_invalid_urls(self):
        for value in ("http://controller", "https://user:key@host", URL + "?key=x",
                      URL + "#key", URL + "/api", "https://api.ui.com"):
            with self.subTest(value=value), self.assertRaises(ControllerError):
                normalize_url(value)

    @patch("core.integrations.unifi.requests.Session")
    def test_local_pagination_metadata_and_tls(self, factory):
        client = {"id": EXTERNAL, "macAddress": "02-00-00-00-00-10", "ipAddress": IP,
                  "name": KEY, "type": "WIRELESS", "ssid": "Home", "signalDbm": -65,
                  "clientUrl": "https://untrusted.example/network/client"}
        factory.return_value.get.side_effect = [
            http_response(status=404), page([{"id": SITE, "name": "Home"}]),
            page([client], total=2),
            page([{"id": SITE, "type": "VPN"}], offset=1, total=2),
        ]
        with UniFiProvider(URL, KEY, False) as provider:
            clients, count = provider.sync_devices(SITE)
        self.assertEqual(count, 2)
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["mac"], MAC)
        self.assertEqual(clients[0]["metadata"]["rssi"], -65)
        self.assertNotIn("name", clients[0]["metadata"])
        self.assertNotIn("client_url", clients[0]["metadata"])
        calls = factory.return_value.get.call_args_list
        self.assertEqual(calls[1].args[0], URL + "/integration/v1/sites")
        self.assertEqual(calls[-1].kwargs["params"]["offset"], 1)
        self.assertTrue(all(not call.kwargs["verify"] and not call.kwargs["allow_redirects"] for call in calls))
        self.assertTrue(all(call.kwargs["headers"]["X-API-Key"] == KEY for call in calls))

    @patch("core.integrations.unifi.requests.Session")
    def test_error_messages_never_include_upstream_content(self, factory):
        get = factory.return_value.get
        for failure in (http_response(status=401), http_response(status=302), page([], total=1),
                        http_response(content=b"<html>not JSON</html>"),
                        requests.Timeout(KEY), requests.exceptions.SSLError(KEY)):
            get.side_effect = [failure]
            with UniFiProvider(URL, KEY, True) as provider, self.assertRaises(ControllerError) as error:
                provider.list_sites()
            self.assertNotIn(KEY, str(error.exception))
            self.assertTrue(get.call_args.kwargs["verify"])


class ControllerIntegrationTests(TestCase):
    def setUp(self):
        self.connection = ControllerConnection.objects.create(
            provider="unifi", enabled=True, url=URL, api_key=KEY, site_id=SITE,
        )
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("controller-admin", is_staff=True))
        self.row = dict(mac=MAC, ip=IP, external_id=EXTERNAL, hostname="office-laptop", vendor="Example",
                        metadata={"site_id": SITE, "site_name": "Home", "connection": "WIRED"})

    def mock_provider(self, rows):
        class Provider:
            def __init__(self, *credentials):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def sync_devices(self, site):
                return rows, len(rows)

        return patch.dict("core.integrations.controllers.PROVIDERS", {"unifi": Provider})

    def test_create_enrich_and_idempotency_without_offline_on_omission(self):
        with self.mock_provider([self.row]):
            self.assertEqual(sync_connection("unifi")["created"], 1)
            self.assertEqual(sync_connection("unifi")["status"], "not_due")
            self.assertEqual(sync_connection("unifi", manual=True)["updated"], 1)
        device = Device.objects.get(mac=MAC)
        self.assertFalse(device.known)
        self.assertEqual(device.hostname, "office-laptop")
        self.assertEqual(device.vendor, "Example")
        self.assertEqual(device.status_source, Device.StatusSource.UNIFI)
        self.assertEqual(ControllerDeviceLink.objects.count(), 1)
        with self.mock_provider([]):
            sync_connection("unifi", manual=True)
        device.refresh_from_db()
        self.assertTrue(device.online)
        detail = self.client.get("/api/v1/device/", {"id": device.pk}).data["data"]
        self.assertEqual(detail["controller_observations"][0]["external_id"], EXTERNAL)
        self.assertNotIn(KEY, str(detail))

    def test_protect_known_profile_and_update_network_facts(self):
        device = Device.objects.create(mac=MAC.upper(), ip="192.168.1.50", known=True, online=False,
                                       name="Custom", icon="tv", room="Office", role="tv", comments="Keep")
        with self.mock_provider([self.row]):
            self.assertEqual(sync_connection("unifi")["updated"], 1)
        device.refresh_from_db()
        self.assertEqual((device.name, device.icon, device.room, device.role, device.comments),
                         ("Custom", "tv", "Office", "tv", "Keep"))
        self.assertEqual(device.ip, IP)
        self.assertTrue(device.online)
        self.assertEqual(Device.objects.count(), 1)

    def test_competing_ip_and_duplicate_rows_do_not_overwrite_identity(self):
        owner = Device.objects.create(mac="02:00:00:00:00:11", ip=IP)
        with self.mock_provider([self.row]):
            self.assertEqual(sync_connection("unifi")["conflicts"], 1)
        owner.refresh_from_db()
        self.assertIn("multiple MAC addresses", owner.identity_conflict_reason)
        self.assertEqual(Device.objects.count(), 1)
        with self.mock_provider([self.row, self.row]):
            self.assertEqual(sync_connection("unifi", manual=True)["skipped"], 2)

    def test_sync_claim_blocks_manual_and_recovers_after_expiration(self):
        ControllerConnection.objects.filter(pk=self.connection.pk).update(lock_until=timezone.now() + timedelta(minutes=1))
        with self.assertRaises(ControllerBusy):
            sync_connection("unifi", manual=True)
        ControllerConnection.objects.filter(pk=self.connection.pk).update(lock_until=timezone.now() - timedelta(seconds=1))
        with self.mock_provider([]):
            self.assertEqual(sync_connection("unifi")["status"], "ok")

    def test_scheduler_honors_interval_and_failed_attempts(self):
        with self.mock_provider([]):
            self.assertEqual(sync_connection("unifi")["status"], "ok")
            self.assertEqual(sync_connection("unifi")["status"], "not_due")
        ControllerConnection.objects.filter(pk=self.connection.pk).update(
            last_attempt_at=timezone.now() - timedelta(minutes=6),
        )
        with patch.object(UniFiProvider, "sync_devices", side_effect=ControllerError("UniFi denied access.")):
            with self.assertRaises(ControllerError):
                sync_connection("unifi")
            self.assertEqual(sync_connection("unifi")["status"], "not_due")
        self.connection.refresh_from_db()
        self.assertIsNone(self.connection.lock_until)
        self.assertEqual(self.connection.last_error, "UniFi denied access.")

    def test_write_only_secret_and_no_retargeting_with_blank_key(self):
        self.assertNotIn(KEY, str(self.client.get(BASE).data))
        payload = dict(enabled=True, url=URL, site_id=SITE, verify_ssl=True, sync_interval=7, api_key="")
        response = self.client.put(BASE, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("api_key", response.data["data"])
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.api_key, KEY)
        self.assertEqual(self.client.put(BASE, {**payload, "url": "https://elsewhere.example"}, format="json").status_code, 400)
        self.client.force_authenticate(User.objects.create_user("controller-viewer"))
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(self.client.post(BASE + "sync/").status_code, 403)

    @patch("core.integrations.unifi.requests.Session")
    def test_discover_sites_and_verify_selected_site_without_creating_devices(self, factory):
        sites = [{"id": SITE, "name": "Home"}]
        factory.return_value.get.side_effect = [page(sites), page(sites), page([])]
        creds = {"url": URL, "api_key": "", "site_id": SITE}
        self.assertEqual(self.client.post(BASE + "sites/", creds, format="json").data["data"]["sites"], sites)
        self.assertEqual(self.client.post(BASE + "test/", creds, format="json").data["data"]["clients_reported"], 0)
        self.assertFalse(Device.objects.exists())
