import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from ..integrations.openwrt import (
    EMPTY_SESSION, MAX_BYTES, OpenWrtAuthError, OpenWrtError,
    _lease_clients, inspect_openwrt, normalize_openwrt_url, sync_openwrt,
)
from ..models import AppSettings, Device
from ..serializers.devices import DeviceInterfaceSerializer, DeviceSerializer
from .test_asuswrt import http_response

URL = "https://router.example"
MAC = "02:00:00:00:00:01"
OTHER = "02:00:00:00:00:02"
IP = "192.168.1.20"
TOKEN = "a" * 32
LEASE = {"macaddr": MAC.upper(), "ipaddr": IP, "expires": 600, "hostname": "test-laptop", "interface": "br-lan"}


class OpenWrtProtocolTests(SimpleTestCase):
    def test_normalize_ubus_url(self):
        self.assertEqual(normalize_openwrt_url("https://ROUTER.example/ubus/"), URL)
        for suffix in ("/cgi-bin/luci", "/ubus?x=y", "/ubus#x", "/ubus\n/fake"):
            with self.subTest(suffix=suffix), self.assertRaises(OpenWrtError):
                normalize_openwrt_url(URL + suffix)
        with self.assertRaises(OpenWrtError):
            normalize_openwrt_url("https://user:password@router.example/ubus")

    @patch("core.integrations.openwrt.requests.Session")
    def test_allowlisted_calls_and_multi_radio_observations(self, session_factory):
        def reply(url, **kwargs):
            self.assertEqual(url, URL + "/ubus")
            self.assertTrue(kwargs["verify"])
            self.assertFalse(kwargs["allow_redirects"])
            rpc = kwargs["json"]
            token, obj, method, args = rpc["params"]
            self.assertEqual(token, EMPTY_SESSION if method == "login" else TOKEN)
            key = obj, method
            if key == ("iwinfo", "assoclist"):
                self.assertIn(args["device"], ["phy0-ap0", "phy1-ap0"])
                data = {"results": [{"mac": MAC.upper(), "signal": 2**32 - 61}]}
            else:
                data = {
                    ("session", "login"): {"ubus_rpc_session": TOKEN},
                    ("luci-rpc", "getDHCPLeases"): {"dhcp_leases": [LEASE]},
                    ("luci-rpc", "getHostHints"): {MAC.upper(): {"ip6addrs": ["fd00::20"]}},
                    ("luci-rpc", "getWirelessDevices"): {
                        "radio0": {"interfaces": [
                            {"ifname": "phy0-ap0", "config": {"mode": "ap", "network": ["lan"], "ssid": "Home"}},
                            {"ifname": "run-this;not-a-device", "config": {"mode": "ap"}},
                        ]},
                        "radio1": {"interfaces": [{"ifname": "phy1-ap0", "config": {"mode": "ap", "ssid": "Guest"}}]},
                    },
                    ("session", "destroy"): {},
                }[key]
            return http_response({"jsonrpc": "2.0", "id": rpc["id"], "result": [0, data]})

        session = session_factory.return_value
        session.post.side_effect = reply
        leases, observations, summary = inspect_openwrt(URL, "inventory", "secret")
        self.assertEqual(leases[0]["ip"], IP)
        self.assertEqual(observations[MAC]["hint_addresses"], ["fd00::20"])
        self.assertEqual([(item["radio"], item["ssid"], item["rssi"]) for item in observations[MAC]["wireless"]],
                         [("radio0", "Home", -61), ("radio1", "Guest", -61)])
        self.assertEqual(summary["wireless_clients"], 1)
        self.assertEqual(session.post.call_count, 7)
        self.assertFalse(session.trust_env)
        session.close.assert_called_once()

    @patch("core.integrations.openwrt.requests.Session")
    def test_partial_acl_support(self, session_factory):
        responses = [
            {"result": [0, {"ubus_rpc_session": TOKEN}]},
            {"error": {"code": -32002, "message": "private detail"}},
            {"result": [0, {MAC: {"ipaddrs": [IP]}}]},
            {"error": {"code": -32000}},
            {"result": [0]},
        ]
        session_factory.return_value.post.side_effect = [
            http_response({"jsonrpc": "2.0", "id": i, **response}) for i, response in enumerate(responses, 1)
        ]
        leases, observations, summary = inspect_openwrt(URL, "inventory", "secret")
        self.assertEqual(leases, [])
        self.assertEqual(observations[MAC]["hint_addresses"], [IP])
        self.assertEqual(summary["unavailable"], ["leases", "wireless"])
        self.assertNotIn("private detail", json.dumps(summary))

    @patch("core.integrations.openwrt.requests.Session")
    def test_auth_failure_does_not_retry(self, session_factory):
        session = session_factory.return_value
        session.post.return_value = http_response({"jsonrpc": "2.0", "id": 1, "result": [6]})
        with self.assertRaises(OpenWrtAuthError):
            inspect_openwrt(URL, "inventory", "secret")
        session.post.assert_called_once()
        session.close.assert_called_once()

    @patch("core.integrations.openwrt.requests.Session")
    def test_invalid_transport_responses(self, session_factory):
        for response in (http_response(status=302), http_response(content=b"x" * (MAX_BYTES + 1)),
                         http_response(content=b"<html>Login</html>"),
                         http_response({"jsonrpc": "2.0", "id": 99, "result": [0]})):
            session_factory.return_value.post.return_value = response
            with self.assertRaises(OpenWrtError):
                inspect_openwrt(URL, "inventory", "secret")

    def test_lease_validation_and_collisions(self):
        self.assertEqual(len(_lease_clients({"dhcp_leases": [dict(LEASE, expires=False)]})), 1)
        for rows in (
            [dict(LEASE, expires=0)], [dict(LEASE, macaddr="ff:ff:ff:ff:ff:ff")],
            [LEASE, dict(LEASE, macaddr=OTHER)], [LEASE, dict(LEASE, ipaddr="192.168.1.21")],
        ):
            self.assertEqual(_lease_clients({"dhcp_leases": rows}), [])


class OpenWrtIntegrationTests(TestCase):
    def setUp(self):
        self.config = AppSettings.load()
        self.config.openwrt_enabled = True
        self.config.openwrt_url = URL
        self.config.openwrt_username = "inventory"
        self.config.openwrt_password = "router-secret"
        self.config.save()
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("admin", is_staff=True))
        self.observations = {MAC: {"name": "test-laptop", "lease_ip": IP},
                             OTHER: {"hint_addresses": ["192.168.1.30"]}}
        self.summary = {"leases": 1, "host_hints": 1, "wireless_clients": 0, "unavailable": []}

    @patch("core.integrations.openwrt.inspect_openwrt")
    def test_only_lease_discovery_is_opt_in(self, inspect):
        inspect.side_effect = lambda *args: (_lease_clients({"dhcp_leases": [LEASE]}), self.observations, self.summary.copy())
        self.assertEqual(sync_openwrt()["devices_discovered"], 0)
        self.config.refresh_from_db()
        self.config.openwrt_create_devices = True
        self.config.save()
        self.assertEqual(sync_openwrt()["devices_discovered"], 1)
        device = Device.objects.get()
        self.assertFalse(device.online)
        self.assertFalse(device.known)
        self.assertEqual(device.hostname_source, Device.IdentitySource.OPENWRT)
        self.assertIn("observed_at", DeviceInterfaceSerializer(device).data["openwrt_data"])
        self.assertEqual(DeviceSerializer(device).data["openwrt_data"]["lease_ip"], IP)

    @patch("core.integrations.openwrt.inspect_openwrt")
    def test_existing_identity_ip_presence_and_archive_are_preserved(self, inspect):
        device = Device.objects.create(mac=MAC, ip="192.168.1.99", name="My laptop", known=True, online=True)
        archived = Device.objects.create(mac=OTHER, ip="192.168.1.30", archived=True)
        self.observations[MAC]["wireless"] = [{"interface": "phy0-ap0"}]
        inspect.return_value = (_lease_clients({"dhcp_leases": [LEASE]}), self.observations, self.summary)
        self.assertEqual(sync_openwrt()["clients_enriched"], 1)
        device.refresh_from_db()
        archived.refresh_from_db()
        self.assertEqual((device.name, device.ip, device.online), ("My laptop", "192.168.1.99", True))
        self.assertNotIn("lease_ip", device.openwrt_data)
        self.assertEqual(archived.openwrt_data, {})

    @patch("core.integrations.openwrt.inspect_openwrt")
    def test_auth_failure_pauses_scheduler_until_manual_sync(self, inspect):
        inspect.side_effect = OpenWrtAuthError("Login rejected.")
        with self.assertRaises(OpenWrtAuthError):
            sync_openwrt()
        self.assertEqual(sync_openwrt()["status"], "auth_paused")
        inspect.assert_called_once()
        inspect.side_effect = None
        inspect.return_value = ([], {}, self.summary)
        self.assertEqual(sync_openwrt(manual=True)["status"], "ok")
        self.config.refresh_from_db()
        self.assertFalse(self.config.openwrt_auth_failed)

    @patch("core.views.openwrt.inspect_openwrt")
    def test_admin_connection_test_does_not_sync_or_reuse_other_router_password(self, inspect):
        inspect.return_value = ([], {}, self.summary)
        endpoint = "/api/v1/integrations/openwrt/test/"
        payload = {"url": URL + "/ubus", "username": "inventory"}
        self.assertEqual(self.client.post(endpoint, payload, format="json").status_code, 200)
        inspect.assert_called_once_with(url=URL, username="inventory", password="router-secret", verify_ssl=True)
        self.assertEqual(self.client.post(endpoint, dict(payload, url="https://other.example"), format="json").status_code, 400)
        self.assertFalse(Device.objects.exists())
        self.client.force_authenticate(User.objects.create_user("viewer"))
        self.assertEqual(self.client.post(endpoint, payload, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/integrations/openwrt/sync/").status_code, 403)

    def test_settings_never_return_password_and_require_it_on_retarget(self):
        endpoint = "/api/v1/settings/"
        response = self.client.get(endpoint)
        self.assertNotIn("openwrt_password", response.data["data"])
        self.assertTrue(response.data["data"]["openwrt_configured"])
        self.assertEqual(self.client.put(endpoint, {"openwrt_url": "https://other.example"}, format="json").status_code, 400)
        response = self.client.put(endpoint, {"openwrt_verify_ssl": False, "openwrt_password": ""}, format="json")
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.openwrt_password, "router-secret")
