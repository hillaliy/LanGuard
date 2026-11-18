from importlib import import_module
from datetime import timedelta
from unittest.mock import patch

import requests
from django.apps import apps
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..integrations.controllers import ControllerBusy, sync_connection
from ..integrations.omada import OmadaProvider, normalize_url
from ..integrations.unifi import ControllerError
from ..models import ControllerConnection, ControllerDeviceLink, Device
from .test_asuswrt import http_response

SITE = "640effd1b3f2ae5b912275ec"
CONTROLLER = "beed48c7a2b0ea97c9698408843119f3"
CLIENT = "38f2d1b616434374b3f3215246f39940"
SECRET = "omada-test-secret"
TOKEN = "AT-memory-only"
MAC = "02:00:00:00:00:20"
IP = "192.168.1.20"
URL = "https://controller.example:8043"
BASE = "/api/v1/integrations/controllers/omada/"


def response(result, code=0):
    return http_response({"errorCode": code, "msg": SECRET, "result": result})


def grid(rows, *, page=1, total=None):
    return response({"data": rows, "totalRows": len(rows) if total is None else total,
                     "currentPage": page, "currentSize": len(rows)})


def provider():
    return OmadaProvider(URL, SECRET, True, controller_id=CONTROLLER, client_id=CLIENT)


def client_row(**overrides):
    return dict(mac=MAC.upper().replace(":", "-"), ip=IP, active=True, name="Office laptop",
                hostName="office-laptop", vendor="Example", wireless=True, ssid="Office",
                connectDevType="ap", apName="Office AP", rssi=-58, signalLevel=74,
                radioId=3, channel=37, **overrides)


def login():
    return response({"accessToken": TOKEN, "expiresIn": 7200, "refreshToken": "never-stored"})


class OmadaProtocolTests(SimpleTestCase):
    def test_url_scope(self):
        self.assertEqual(normalize_url(" https://CONTROLLER.example:8043/ "), URL)
        for url in ("http://controller", URL + "/openapi", URL + "/?x=y", URL + "/#secret",
                    "https://user:pass@controller", "https://controller:0", "https://controller:bad",
                    "https://use1-omada-northbound.tplinkcloud.com", URL + "\n/"):
            with self.subTest(url=url), self.assertRaises(ControllerError):
                normalize_url(url)

    @patch("core.integrations.omada.requests.Session")
    def test_client_mode_auth_and_get_only_inventory(self, factory):
        session = factory.return_value
        session.post.return_value = login()
        session.get.side_effect = [
            grid([{"siteId": SITE, "name": "Office"}]),
            grid([client_row(), dict(client_row(), active=False), dict(client_row(), active="true")]),
        ]
        with provider() as client:
            rows, total = client.sync_devices(SITE)
        self.assertEqual(total, 3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mac"], MAC)
        self.assertEqual(rows[0]["metadata"]["rssi"], -58)
        self.assertEqual(rows[0]["metadata"]["signal_percent"], 74)
        self.assertEqual(rows[0]["metadata"]["radio"], "6 GHz")
        self.assertEqual(session.post.call_count, 1)
        call = session.post.call_args
        self.assertEqual(call.args[0], URL + "/openapi/authorize/token")
        self.assertEqual(call.kwargs["params"], {"grant_type": "client_credentials"})
        self.assertEqual(call.kwargs["json"], {"omadacId": CONTROLLER, "client_id": CLIENT, "client_secret": SECRET})
        self.assertTrue(call.kwargs["verify"])
        self.assertFalse(call.kwargs["allow_redirects"])
        self.assertNotIn(SECRET, str(call.kwargs["params"]))
        get = session.get.call_args
        self.assertEqual(get.args[0], URL + f"/openapi/v1/{CONTROLLER}/sites/{SITE}/clients")
        self.assertEqual(get.kwargs["headers"]["Authorization"], f"AccessToken={TOKEN}")
        self.assertFalse(session.trust_env)
        self.assertEqual(client.token, "")
        session.close.assert_called_once()

    @patch("core.integrations.omada.requests.Session")
    def test_complete_pagination_and_empty_page(self, factory):
        factory.return_value.post.return_value = login()
        sites = [{"siteId": f"site{i}", "name": f"Site {i}"} for i in range(201)]
        factory.return_value.get.side_effect = [grid(sites[:200], total=201), grid(sites[200:], page=2, total=201)]
        with provider() as client:
            self.assertEqual(len(client.list_sites()), 201)
        self.assertEqual(factory.return_value.get.call_args.kwargs["params"], {"page": 2, "pageSize": 200})

    @patch("core.integrations.omada.requests.Session")
    def test_malformed_page_and_duplicate_sites_fail_without_partial_results(self, factory):
        for result in [
            grid([], total=1), grid([{"siteId": "../outside"}]),
            grid([{"siteId": SITE}, {"siteId": SITE}]),
            response({"data": [], "currentPage": 1, "totalRows": True}),
            grid([], page=9), grid([], total=1001),
        ]:
            factory.return_value.post.return_value = login()
            factory.return_value.get.return_value = result
            with provider() as client, self.assertRaises(ControllerError):
                client.list_sites()

    @patch("core.integrations.omada.requests.Session")
    def test_auth_http_tls_and_json_failures_are_safe(self, factory):
        for failure in [
            response({}, code=-44106), http_response(status=401), http_response(status=302),
            requests.Timeout(SECRET), requests.exceptions.SSLError(SECRET),
            http_response(content=b"<html>login</html>"), http_response(content=b"x" * (2 * 1024 * 1024 + 1)),
            response({"accessToken": "invalid\nheader", "expiresIn": 7200}),
            response({"accessToken": TOKEN, "expiresIn": 0}),
        ]:
            factory.return_value.post.side_effect = [failure]
            with provider() as client, self.assertRaises(ControllerError) as error:
                client.list_sites()
            self.assertNotIn(SECRET, str(error.exception))
            self.assertEqual(factory.return_value.get.call_count, 0)

    @patch("core.integrations.omada.requests.Session")
    def test_reflected_secrets_are_not_metadata_and_unknown_site_fails(self, factory):
        session = factory.return_value
        session.post.return_value = login()
        session.get.side_effect = [grid([{"siteId": SITE, "name": TOKEN}]),
                                   grid([dict(client_row(), name=SECRET, ssid=TOKEN)])]
        with provider() as client:
            rows, _ = client.sync_devices(SITE)
        self.assertEqual(rows[0]["metadata"]["site_name"], "Unnamed site")
        self.assertNotIn("ssid", rows[0]["metadata"])
        self.assertNotIn("name", rows[0]["metadata"])
        session.get.return_value = grid([])
        session.get.side_effect = None
        with provider() as client, self.assertRaises(ControllerError):
            client.test_connection("nonexistent")


class OmadaIntegrationTests(TestCase):
    def setUp(self):
        self.connection = ControllerConnection.objects.create(
            provider="omada", enabled=True, url=URL, api_key=SECRET, controller_id=CONTROLLER,
            client_id=CLIENT, site_id=SITE,
        )
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("omada-admin", is_staff=True))
        self.payload = dict(enabled=True, url=URL, controller_id=CONTROLLER, client_id=CLIENT,
                            client_secret="", site_id=SITE, verify_ssl=True, sync_interval=5)

    def protocol(self, factory, rows):
        factory.return_value.post.return_value = login()
        factory.return_value.get.side_effect = [grid([{"siteId": SITE, "name": "Office"}]), grid(rows)]

    @patch("core.integrations.omada.requests.Session")
    def test_full_sync_discovery_positive_presence_and_absence(self, factory):
        self.protocol(factory, [client_row()])
        self.assertEqual(sync_connection("omada")["created"], 1)
        device = Device.objects.get(mac=MAC)
        self.assertFalse(device.known)
        self.assertTrue(device.online)
        self.assertEqual(device.status_source, "omada")
        self.assertEqual(device.vendor, "Example")
        self.protocol(factory, [client_row()])
        self.assertEqual(sync_connection("omada", manual=True)["updated"], 1)
        self.assertEqual(ControllerDeviceLink.objects.count(), 1)
        self.protocol(factory, [])
        sync_connection("omada", manual=True)
        device.refresh_from_db()
        self.assertTrue(device.online)
        detail = self.client.get("/api/v1/device/", {"id": device.pk}).data["data"]
        self.assertEqual(detail["controller_observations"][0]["provider"], "omada")
        self.assertNotIn(SECRET, str(detail))

    @patch("core.integrations.omada.requests.Session")
    def test_known_profile_duplicate_mac_and_ip_conflicts(self, factory):
        device = Device.objects.create(mac=MAC, ip="192.168.1.99", known=True,
                                       name="Custom", icon="tv", room="Office", comments="Keep")
        self.protocol(factory, [client_row()])
        self.assertEqual(sync_connection("omada")["updated"], 1)
        device.refresh_from_db()
        self.assertEqual((device.name, device.icon, device.room, device.comments, device.ip),
                         ("Custom", "tv", "Office", "Keep", IP))
        self.protocol(factory, [client_row(), client_row()])
        self.assertEqual(sync_connection("omada", manual=True)["skipped"], 2)
        Device.objects.create(mac="02:00:00:00:00:21", ip=IP)
        self.protocol(factory, [client_row()])
        self.assertEqual(sync_connection("omada", manual=True)["conflicts"], 1)

    def test_write_only_secret_preservation_and_binding(self):
        response = self.client.get(BASE)
        self.assertNotIn(SECRET, str(response.data))
        self.assertNotIn("api_key", response.data["data"])
        self.assertEqual(response.data["data"]["site_id"], SITE)
        self.assertEqual(self.client.put(BASE, self.payload, format="json").status_code, 200)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.api_key, SECRET)
        for field, value in (("url", "https://other.example"), ("controller_id", "different"), ("client_id", "different")):
            self.assertEqual(self.client.put(BASE, {**self.payload, field: value}, format="json").status_code, 400)
        self.assertEqual(self.client.put(BASE, {**self.payload, "client_secret": "new-secret",
                                               "controller_id": "different"}, format="json").status_code, 200)

    @patch("core.integrations.omada.requests.Session")
    def test_test_action_sites_and_disabled_or_unauthorized_sync(self, factory):
        factory.return_value.post.return_value = login()
        factory.return_value.get.return_value = grid([{"siteId": SITE, "name": "Office"}])
        result = self.client.post(BASE + "sites/", {**self.payload, "site_id": None}, format="json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["data"]["sites"][0]["id"], SITE)
        self.assertFalse(Device.objects.exists())
        self.client.force_authenticate(User.objects.create_user("viewer"))
        for path in (BASE, BASE + "sites/", BASE + "test/", BASE + "sync/"):
            self.assertEqual(self.client.post(path, self.payload, format="json").status_code, 403)
        with self.assertRaises(ControllerBusy):
            self.connection.lock_until = timezone.now() + timedelta(minutes=1)
            self.connection.save()
            sync_connection("omada", manual=True)

    @patch("core.integrations.omada.requests.Session")
    def test_failed_auth_is_saved_safely_and_scheduler_waits_until_due(self, factory):
        factory.return_value.post.return_value = response({}, code=-44106)
        with self.assertRaises(ControllerError):
            sync_connection("omada")
        self.connection.refresh_from_db()
        self.assertNotIn(SECRET, self.connection.last_error)
        self.assertTrue(self.connection.last_error)
        self.assertIsNone(self.connection.lock_until)
        self.assertEqual(sync_connection("omada")["status"], "not_due")
        factory.return_value.post.assert_called_once()

    def test_existing_unifi_site_identifier_normalization(self):
        connection = ControllerConnection.objects.create(provider="unifi", site_id="10000000000040008000000000000001")
        migration = import_module("core.migrations.0062_omada_controller")
        migration.preserve_unifi_site_ids(apps, None)
        connection.refresh_from_db()
        self.assertEqual(connection.site_id, "10000000-0000-4000-8000-000000000001")
