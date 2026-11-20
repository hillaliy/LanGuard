from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..integrations.controllers import ControllerBusy, sync_connection, sync_due_connections
from ..integrations.routeros import MENUS, RouterOSProvider, normalize_url
from ..integrations.unifi import ControllerError
from ..models import ControllerConnection, ControllerDeviceLink, Device
from .test_asuswrt import http_response

URL = "https://router.example:8443"
PASSWORD = "routeros-test-password"
MAC = "02:00:00:00:00:30"
IP = "192.168.88.30"
BASE = "/api/v1/integrations/controllers/routeros/"


def tables(**overrides):
    data = {key: [] for key in MENUS}
    data.update({"system/resource": [{"version": "7.20.1 (stable)"}],
                 "system/identity": [{"name": "Office router"}],
                 "ip/arp": [{"mac-address": MAC, "address": IP, "status": "reachable", "interface": "bridge"}],
                 "ip/dhcp-server/lease": [{"mac-address": MAC, "address": IP, "host-name": "office-laptop",
                                           "status": "bound", "server": "dhcp1"}],
                 "interface/bridge/host": [{"mac-address": MAC, "bridge": "bridge", "on-interface": "ether2", "vid": "10"}]})
    data.update(overrides)
    return data


def protocol(factory, data):
    def get(url, **kwargs):
        value = data[url.split("/rest/", 1)[1]]
        return value if hasattr(value, "status_code") else http_response(value)
    factory.return_value.get.side_effect = get


def provider():
    return RouterOSProvider(URL, PASSWORD, True, username="monitoring")


class RouterOSProtocolTests(SimpleTestCase):
    def test_url_validation_and_basic_credentials(self):
        self.assertEqual(normalize_url(" https://ROUTER.example:8443/ "), URL)
        for url in ("http://router", URL + "/rest", URL + "?password=x", URL + "#x",
                    "https://a:b@router", "https://router:0", "https://router:bad", URL + "\n/"):
            with self.subTest(url=url), self.assertRaises(ControllerError):
                normalize_url(url)
        for username, password in (("", PASSWORD), ("a:b", PASSWORD), ("a", "x\n"), ("a", "סוד")):
            with self.assertRaises(ControllerError):
                RouterOSProvider(URL, password, True, username=username)

    @patch("core.integrations.routeros.requests.Session")
    def test_get_only_auth_and_lease_bridge_enrichment(self, factory):
        protocol(factory, tables())
        with provider() as client:
            rows, total = client.sync_devices()
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ip"], IP)
        self.assertTrue(rows[0]["presence"])
        self.assertEqual(rows[0]["metadata"]["vlan"], 10)
        self.assertEqual(rows[0]["metadata"]["bridge"], "bridge")
        self.assertEqual(rows[0]["metadata"]["interface"], "ether2")
        self.assertNotIn("connection", rows[0]["metadata"])  # Bridge learning does not prove Ethernet.
        self.assertEqual(rows[0]["hostname"], "office-laptop")
        session = factory.return_value
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_count, len(MENUS))
        for call in session.get.call_args_list:
            self.assertEqual(call.kwargs["auth"], ("monitoring", PASSWORD))
            self.assertTrue(call.kwargs["verify"])
            self.assertFalse(call.kwargs["allow_redirects"])
            self.assertIn(".proplist", call.kwargs["params"])
            self.assertNotIn(PASSWORD, call.args[0])
        session.post.assert_not_called()
        session.put.assert_not_called()
        session.close.assert_called_once()

    @patch("core.integrations.routeros.requests.Session")
    def test_only_reachable_arp_not_complete_static_stale_or_dhcp(self, factory):
        for state in ("stale", "permanent", "failed", "delay", "probe", "incomplete", ""):
            data = tables()
            data["ip/arp"][0].update(status=state, complete="true")
            protocol(factory, data)
            with provider() as client:
                rows, _ = client.sync_devices()
            self.assertFalse(rows[0]["presence"])

    @patch("core.integrations.routeros.requests.Session")
    def test_new_wifi_authorization_and_string_metrics(self, factory):
        data = tables(**{"ip/arp": [], "interface/bridge/host": [],
                         "interface/wifi/registration-table": [{"mac-address": MAC, "authorized": "true",
                           "interface": "wifi1", "ssid": "Office", "signal": "-61", "vlan-id": "20"}]})
        protocol(factory, data)
        with provider() as client:
            rows, _ = client.sync_devices()
        self.assertEqual(rows[0]["metadata"]["rssi"], -61)
        self.assertEqual(rows[0]["metadata"]["vlan"], 20)
        self.assertEqual(rows[0]["metadata"]["connection"], "WIRELESS")
        for flag in ("false", "yes please", "1", None):
            data["interface/wifi/registration-table"][0]["authorized"] = flag
            protocol(factory, data)
            with provider() as client:
                rows, _ = client.sync_devices()
            self.assertFalse(rows[0]["presence"])

    @patch("core.integrations.routeros.requests.Session")
    def test_legacy_wifi_and_capsman(self, factory):
        for menu, row in (("interface/wireless/registration-table", {"ap": "false", "signal-strength": "-65dBm@6Mbps"}),
                          ("caps-man/registration-table", {"rx-signal": "-64", "ssid": "Office"})):
            protocol(factory, tables(**{"ip/arp": [], menu: [{"mac-address": MAC, "interface": "wlan1", **row}]}))
            with provider() as client:
                rows, _ = client.sync_devices()
            self.assertTrue(rows[0]["presence"])
            self.assertIn("rssi", rows[0]["metadata"])

    @patch("core.integrations.routeros.requests.Session")
    def test_optional_missing_packages_warn_but_auth_failure_aborts(self, factory):
        data = tables(**{"interface/wifi/registration-table": http_response(status=404)})
        protocol(factory, data)
        with provider() as client:
            self.assertEqual(client.test_connection()["warnings"], ["Unavailable menu: interface/wifi/registration-table"])
        for status in (401, 403, 302, 500):
            data["interface/wifi/registration-table"] = http_response(status=status)
            protocol(factory, data)
            with provider() as client, self.assertRaises(ControllerError):
                client.sync_devices()

    @patch("core.integrations.routeros.requests.Session")
    def test_all_inventory_missing_and_old_or_beta_firmware_fail(self, factory):
        data = {menu: http_response(status=404) for menu in MENUS}
        data.update({key: value for key, value in tables().items() if key.startswith("system/")})
        protocol(factory, data)
        with provider() as client, self.assertRaises(ControllerError):
            client.sync_devices()
        for version in ("6.49.17", "7.0", "7.21beta1", "garbage"):
            protocol(factory, tables(**{"system/resource": [{"version": version}]}))
            with provider() as client, self.assertRaises(ControllerError):
                client.sync_devices()

    @patch("core.integrations.routeros.requests.Session")
    def test_safe_errors_malformed_oversized_and_timeout(self, factory):
        for failure in (requests.Timeout(PASSWORD), requests.exceptions.SSLError(PASSWORD),
                        requests.ConnectionError(PASSWORD), http_response(content=b"<html>"),
                        http_response({"error": 500, "message": PASSWORD}), http_response([None]),
                        http_response([{}] * 5001), http_response(content=b"x" * (2 * 1024 * 1024 + 1))):
            factory.return_value.get.side_effect = [failure]
            with provider() as client, self.assertRaises(ControllerError) as error:
                client.sync_devices()
            self.assertNotIn(PASSWORD, str(error.exception))
        with provider() as client, self.assertRaises(ControllerError):
            client.deadline = 0
            client.sync_devices()

    @patch("core.integrations.routeros.requests.Session")
    def test_duplicate_leases_or_multiple_ips_or_vlan_context_are_skipped(self, factory):
        for change in ("lease", "ip", "vlan", "bridge", "interface", "wifi"):
            data = tables()
            if change == "lease":
                data["ip/dhcp-server/lease"] *= 2
            elif change == "ip":
                data["ip/arp"].append({"mac-address": MAC, "address": "192.168.88.31", "status": "reachable"})
            elif change == "vlan":
                data["interface/bridge/host"].append({"mac-address": MAC, "vid": "20"})
            elif change in ("bridge", "interface"):
                data["interface/bridge/host"].append({"mac-address": MAC, "bridge": "other",
                                                     "on-interface": "ether3"})
            else:
                data["interface/wifi/registration-table"] = [{"mac-address": MAC, "authorized": "true"}] * 2
            protocol(factory, data)
            with provider() as client:
                self.assertEqual(client.sync_devices(), ([], 1))

    @patch("core.integrations.routeros.requests.Session")
    def test_disabled_proxy_and_reflected_credentials_are_not_observations(self, factory):
        data = tables(**{"system/identity": [{"name": PASSWORD}]})
        data["ip/arp"][0]["published"] = "true"
        data["ip/dhcp-server/lease"][0]["host-name"] = PASSWORD
        protocol(factory, data)
        with provider() as client:
            rows, _ = client.sync_devices()
            self.assertEqual(client.label(client.encoded_auth), "")
        self.assertFalse(rows[0]["presence"])
        self.assertNotIn(PASSWORD, str(rows))


class RouterOSIntegrationTests(TestCase):
    def setUp(self):
        self.connection = ControllerConnection.objects.create(provider="routeros", url=URL, api_key=PASSWORD,
                                                              username="monitoring", enabled=True)
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("routeros-admin", is_staff=True))
        self.payload = dict(url=URL, username="monitoring", password="", enabled=True,
                            verify_ssl=True, sync_interval=5)

    @patch("core.integrations.routeros.requests.Session")
    def test_discovery_known_profile_preserved_absence_and_idempotence(self, factory):
        protocol(factory, tables())
        self.assertEqual(sync_connection("routeros")["created"], 1)
        device = Device.objects.get(mac=MAC)
        self.assertFalse(device.known)
        self.assertTrue(device.online)
        self.assertEqual(device.status_source, "routeros")
        device.known, device.name, device.icon, device.room = True, "Custom", "tv", "Office"
        device.save()
        self.assertEqual(sync_connection("routeros", manual=True)["updated"], 1)
        device.refresh_from_db()
        self.assertEqual((device.name, device.icon, device.room), ("Custom", "tv", "Office"))
        self.assertEqual(ControllerDeviceLink.objects.count(), 1)
        protocol(factory, tables(**{key: [] for key in MENUS if not key.startswith("system/")}))
        sync_connection("routeros", manual=True)
        device.refresh_from_db()
        self.assertTrue(device.online)
        detail = self.client.get("/api/v1/device/", {"id": device.pk}).data["data"]
        self.assertEqual(detail["controller_observations"][0]["provider"], "routeros")
        self.assertNotIn(PASSWORD, str(detail))

    @patch("core.integrations.routeros.requests.Session")
    def test_passive_context_does_not_create_or_modify_presence_ip_or_identity(self, factory):
        data = tables(**{"ip/arp": []})
        protocol(factory, data)
        self.assertEqual(sync_connection("routeros")["skipped"], 1)
        self.assertFalse(Device.objects.exists())
        device = Device.objects.create(mac=MAC, ip="192.168.88.99", known=True, online=False,
                                       lastseen=timezone.now() - timedelta(days=1))
        before = device.lastseen
        self.assertEqual(sync_connection("routeros", manual=True)["updated"], 1)
        device.refresh_from_db()
        self.assertFalse(device.online)
        self.assertEqual(device.lastseen, before)
        self.assertEqual(device.ip, "192.168.88.99")
        self.assertEqual(ControllerDeviceLink.objects.get().metadata["reported_ip"], IP)

    @patch("core.integrations.routeros.requests.Session")
    def test_ip_conflict_archived_and_due_protection(self, factory):
        protocol(factory, tables())
        Device.objects.create(mac="02:00:00:00:00:31", ip=IP)
        self.assertEqual(sync_connection("routeros")["conflicts"], 1)
        self.assertEqual(sync_connection("routeros")["status"], "not_due")
        Device.objects.all().delete()
        Device.objects.create(mac=MAC, ip=IP, archived=True)
        self.assertEqual(sync_connection("routeros", manual=True)["skipped"], 1)

    def test_secret_is_write_only_bound_to_origin_and_username(self):
        self.assertEqual(self.client.put(BASE, self.payload, format="json").status_code, 200)
        data = self.client.get(BASE).data["data"]
        self.assertTrue(data["configured"])
        self.assertIsNone(data["site_id"])
        self.assertNotIn(PASSWORD, str(data))
        for field, value in (("url", "https://other.example"), ("username", "other")):
            self.assertEqual(self.client.put(BASE, {**self.payload, field: value}, format="json").status_code, 400)
        self.assertEqual(self.client.put(BASE, {**self.payload, "password": " rotated secret ", "username": "new"},
                                        format="json").status_code, 200)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.api_key, " rotated secret ")

    @patch("core.integrations.routeros.requests.Session")
    def test_probe_does_not_write_and_scheduler_persists_safe_failure(self, factory):
        protocol(factory, tables())
        response = self.client.post(BASE + "test/", self.payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["positive_observations"], 1)
        self.assertFalse(Device.objects.exists())
        factory.return_value.get.side_effect = requests.ConnectionError(PASSWORD)
        sync_due_connections()
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.last_error)
        self.assertNotIn(PASSWORD, self.connection.last_error)
        self.assertIsNone(self.connection.lock_until)

    def test_permissions_disabled_and_busy(self):
        self.connection.lock_until = timezone.now() + timedelta(minutes=1)
        self.connection.save()
        with self.assertRaises(ControllerBusy):
            sync_connection("routeros", manual=True)
        self.connection.lock_until, self.connection.enabled = None, False
        self.connection.save()
        self.assertEqual(self.client.post(BASE + "sync/").status_code, 409)
        self.client.force_authenticate(User.objects.create_user("routeros-viewer"))
        self.assertEqual(self.client.get(BASE).status_code, 403)
        for path in (BASE + "test/", BASE + "sites/", BASE + "sync/"):
            self.assertEqual(self.client.post(path, self.payload, format="json").status_code, 403)
