import base64
import json
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..integrations.asuswrt import (
    CLIENT_HOOK, MAX_RESPONSE_BYTES, AsuswrtAuthError, AsuswrtClient, AsuswrtError,
    inspect_asuswrt, normalize_asuswrt_url, parse_clients, sync_asuswrt,
)
from ..models import AppSettings, Device
from ..serializers.devices import DeviceSerializer

MAC = "aa:bb:cc:dd:ee:10"
IP = "192.168.50.10"


def client_payload(**overrides):
    return {"get_clientlist": {MAC.upper(): {
        "mac": MAC.upper(), "ip": IP, "name": "bedroom-lamp", "nickName": "Bedroom lamp",
        "vendor": "Example vendor", "isOnline": "1", "isWL": "1", "rssi": "-62", "ssid": "Home",
        **overrides,
    }}, "productid": "RT-AX88U", "firmver": "3.0.0.4", "buildno": "388", "extendno": "8"}


def http_response(payload=None, *, status=200, content=None):
    response = Mock()
    response.status_code = status
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [content if content is not None else json.dumps(payload).encode()]
    return response


class AsuswrtProtocolTests(SimpleTestCase):
    def test_base_url_rejects_credentials_paths_and_redirect_targets(self):
        self.assertEqual(normalize_asuswrt_url(" https://ROUTER.local:8443/ "), "https://router.local:8443")
        for url in ("ftp://router", "http://user:pass@router", "http://router/appGet.cgi",
                    "http://router/?hook=x", "http://router/#x", "http://router:0", "http://router:bad", "http://"):
            with self.subTest(url=url), self.assertRaises(AsuswrtError):
                normalize_asuswrt_url(url)

    @patch("core.integrations.asuswrt.requests.Session")
    def test_only_login_read_hook_and_logout_are_sent(self, session_factory):
        session = session_factory.return_value
        session.post.side_effect = [http_response({"asus_token": "safe-token"}),
                                    http_response(client_payload()), http_response(content=b"logged out")]
        clients, summary = inspect_asuswrt("https://router.local", "admin", "private-password")
        self.assertEqual(len(clients), 1)
        self.assertEqual(summary["model"], "RT-AX88U")
        calls = session.post.call_args_list
        self.assertEqual([call.args[0].split("/")[-1] for call in calls], ["login.cgi", "appGet.cgi", "Logout.asp"])
        self.assertEqual(base64.b64decode(calls[0].kwargs["data"]["login_authorization"]), b"admin:private-password")
        self.assertEqual(calls[1].kwargs["data"], {"hook": CLIENT_HOOK})
        self.assertEqual(calls[1].kwargs["headers"]["Cookie"], "asus_token=safe-token")
        self.assertTrue(all(call.kwargs["verify"] for call in calls))
        self.assertTrue(all(call.kwargs["allow_redirects"] is False for call in calls))
        self.assertFalse(session.trust_env)
        session.close.assert_called_once()

    @patch("core.integrations.asuswrt.requests.Session")
    def test_authentication_failure_does_not_retry_or_expose_raw_error(self, session_factory):
        session = session_factory.return_value
        session.post.return_value = http_response({"error_status": "3", "secret": "must-not-leak"})
        with self.assertRaises(AsuswrtAuthError) as raised:
            inspect_asuswrt("http://router.local", "admin", "must-not-leak")
        self.assertNotIn("must-not-leak", str(raised.exception))
        session.post.assert_called_once()
        session.close.assert_called_once()

    @patch("core.integrations.asuswrt.requests.Session")
    def test_redirects_are_not_followed(self, session_factory):
        session_factory.return_value.post.return_value = http_response(status=302)
        with self.assertRaisesRegex(AsuswrtError, "redirected"):
            inspect_asuswrt("http://router.local", "admin", "secret")
        session_factory.return_value.post.assert_called_once()

    @patch("core.integrations.asuswrt.requests.Session")
    def test_non_json_and_oversized_responses_fail_safely(self, session_factory):
        for content in (b"<html>Login required</html>", b"x" * (MAX_RESPONSE_BYTES + 1)):
            session_factory.return_value.post.return_value = http_response(content=content)
            with self.subTest(length=len(content)), self.assertRaises(AsuswrtError):
                inspect_asuswrt("http://router.local", "admin", "secret")

    @patch("core.integrations.asuswrt.requests.Session")
    def test_tls_and_timeouts_are_safe_diagnostics(self, session_factory):
        for exception in (requests.exceptions.SSLError("secret"), requests.Timeout("secret"), requests.ConnectionError("secret")):
            session_factory.return_value.post.side_effect = exception
            with self.subTest(exception=type(exception)), self.assertRaises(AsuswrtError) as raised:
                inspect_asuswrt("http://router.local", "admin", "secret")
            self.assertNotIn("secret", str(raised.exception))

    @patch("core.integrations.asuswrt.requests.Session")
    def test_logout_and_close_happen_when_client_payload_is_unsupported(self, session_factory):
        session = session_factory.return_value
        session.post.side_effect = [http_response({"asus_token": "token"}), http_response({}), http_response({})]
        with self.assertRaises(AsuswrtError):
            inspect_asuswrt("http://router.local", "admin", "secret", False)
        self.assertEqual(session.post.call_count, 3)
        self.assertFalse(session.post.call_args_list[0].kwargs["verify"])
        session.close.assert_called_once()

    def test_no_arbitrary_endpoints_are_allowed(self):
        client = AsuswrtClient("http://router.local", "admin", "secret")
        try:
            with self.assertRaises(AsuswrtError):
                client._request("applyapp.cgi", {"rc_service": "reboot"})
            with self.assertRaises(AsuswrtError):
                client._request("appGet.cgi", {"hook": "nvram_set(test,1)"})
        finally:
            client.close()

    def test_real_http_round_trip_against_local_protocol_emulator(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode())
                received.append((self.path, body, self.headers.get("Cookie")))
                payload = {"asus_token": "emulator-token"} if self.path == "/login.cgi" else (
                    client_payload() if self.path == "/appGet.cgi" else {}
                )
                content = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            clients, _ = inspect_asuswrt(f"http://127.0.0.1:{server.server_port}", "admin", "emulator-secret")
            self.assertEqual(clients[0]["mac"], MAC)
            self.assertEqual([item[0] for item in received], ["/login.cgi", "/appGet.cgi", "/Logout.asp"])
            self.assertEqual(received[1][1], {"hook": [CLIENT_HOOK]})
            self.assertEqual(received[1][2], "asus_token=emulator-token")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_active_clients_are_normalized_with_connection_data(self):
        clients, summary = parse_clients(client_payload())
        self.assertEqual(clients[0]["mac"], MAC)
        self.assertEqual(clients[0]["metadata"]["connection"], "Wi-Fi 2.4 GHz")
        self.assertEqual(clients[0]["metadata"]["rssi"], -62)
        self.assertEqual(summary["clients_active"], 1)

    def test_offline_and_invalid_clients_are_not_imported(self):
        for overrides in ({"isOnline": "0"}, {"isOnline": None}, {"ip": "8.8.8.8"}, {"ip": "::1"},
                          {"ip": "bad"}, {"ip": "127.0.0.1"}, {"mac": "aa:bb:cc:dd:ee:20"}):
            with self.subTest(overrides=overrides):
                self.assertEqual(parse_clients(client_payload(**overrides))[0], [])
        with self.assertRaises(AsuswrtError):
            parse_clients({"get_clientlist": []})

    def test_duplicate_ip_records_are_all_skipped(self):
        payload = client_payload()
        payload["get_clientlist"]["aa:bb:cc:dd:ee:20"] = {"ip": IP, "isOnline": "1"}
        clients, summary = parse_clients(payload)
        self.assertEqual(clients, [])
        self.assertEqual(summary["clients_invalid"], 2)


class AsuswrtIntegrationTests(TestCase):
    def setUp(self):
        self.config = AppSettings.load()
        self.config.asuswrt_enabled = True
        self.config.asuswrt_url = "http://router.local"
        self.config.asuswrt_username = "admin"
        self.config.asuswrt_password = "router-secret"
        self.config.save()
        self.user = User.objects.create_user("admin", password="password", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def parsed(self):
        return parse_clients(client_payload())

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_creation_is_opt_in_and_never_marks_clients_online(self, inspect):
        inspect.return_value = self.parsed()
        self.assertEqual(sync_asuswrt()["devices_discovered"], 0)
        self.assertFalse(Device.objects.exists())
        self.config.asuswrt_create_devices = True
        self.config.save()
        self.assertEqual(sync_asuswrt()["devices_discovered"], 1)
        device = Device.objects.get(mac=MAC)
        self.assertFalse(device.online)
        self.assertEqual(device.hostname_source, Device.IdentitySource.ASUSWRT)
        self.assertEqual(device.vendor, "Example vendor")
        self.assertEqual(device.asuswrt_data["ssid"], "Home")
        self.assertNotIn("router-secret", json.dumps(DeviceSerializer(device).data))

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_known_identity_and_presence_are_preserved(self, inspect):
        inspect.return_value = self.parsed()
        before = timezone.now() - timedelta(days=3)
        device = Device.objects.create(mac=MAC, ip=IP, name="My lamp", hostname="user-host",
                                       vendor="Trusted vendor", known=True, online=False, lastseen=before)
        sync_asuswrt()
        device.refresh_from_db()
        self.assertEqual((device.name, device.hostname, device.vendor), ("My lamp", "user-host", "Trusted vendor"))
        self.assertFalse(device.online)
        self.assertEqual(device.lastseen, before)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_enrichment_preserves_stronger_hostname_sources(self, inspect):
        inspect.return_value = self.parsed()
        device = Device.objects.create(mac=MAC, ip=IP, hostname="trusted-host", hostname_source=Device.IdentitySource.MDNS)
        sync_asuswrt()
        device.refresh_from_db()
        self.assertEqual(device.hostname, "trusted-host")

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_conflicting_ip_does_not_create_or_reassign_device(self, inspect):
        inspect.return_value = self.parsed()
        other = Device.objects.create(mac="aa:bb:cc:dd:ee:20", ip=IP)
        self.config.asuswrt_create_devices = True
        self.config.save()
        result = sync_asuswrt()
        self.assertEqual(result["identity_conflicts"], 1)
        self.assertFalse(Device.objects.filter(mac=MAC).exists())
        other.refresh_from_db()
        self.assertTrue(other.identity_conflict_reason)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_auth_failure_pauses_automatic_login_until_manual_recovery(self, inspect):
        inspect.side_effect = AsuswrtAuthError("Login refused")
        with self.assertRaises(AsuswrtAuthError):
            sync_asuswrt()
        self.assertEqual(sync_asuswrt()["status"], "auth_paused")
        inspect.assert_called_once()
        inspect.side_effect = None
        inspect.return_value = self.parsed()
        self.assertEqual(sync_asuswrt(manual=True)["status"], "ok")
        self.config.refresh_from_db()
        self.assertFalse(self.config.asuswrt_auth_failed)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_disabled_integration_does_not_contact_router(self, inspect):
        self.config.asuswrt_enabled = False
        self.config.save()
        self.assertEqual(sync_asuswrt()["status"], "disabled")
        inspect.assert_not_called()

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_settings_change_during_fetch_prevents_inventory_writes(self, inspect):
        def change_settings(*args):
            AppSettings.objects.update(asuswrt_url="http://other-router.local")
            return self.parsed()
        inspect.side_effect = change_settings
        with self.assertRaises(AsuswrtError):
            sync_asuswrt()
        self.assertFalse(Device.objects.exists())

    @patch("core.views.asuswrt.inspect_asuswrt")
    def test_test_endpoint_does_not_modify_devices_or_return_credentials(self, inspect):
        inspect.return_value = self.parsed()
        response = self.client.post("/api/v1/integrations/asuswrt/test/",
                                    {"url": "http://router.local", "username": "admin"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Device.objects.exists())
        self.assertNotIn("router-secret", json.dumps(response.data))
        inspect.assert_called_once_with("http://router.local", "admin", "router-secret", True)

    @patch("core.views.asuswrt.inspect_asuswrt")
    def test_saved_password_cannot_be_reused_for_different_router_or_user(self, inspect):
        for url, username in (("http://other-router.local", "admin"), ("http://router.local", "other")):
            response = self.client.post("/api/v1/integrations/asuswrt/test/",
                                        {"url": url, "username": username}, format="json")
            self.assertEqual(response.status_code, 400)
        inspect.assert_not_called()

    def test_settings_keep_password_private_and_require_new_credentials_for_target_changes(self):
        response = self.client.get("/api/v1/settings/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["asuswrt_configured"])
        self.assertNotIn("asuswrt_password", response.data["data"])
        for body in ({"asuswrt_url": "http://other-router.local"}, {"asuswrt_username": "other"},
                     {"asuswrt_sync_interval": 0}, {"asuswrt_sync_interval": 1441}, {"asuswrt_url": ""}):
            response = self.client.put("/api/v1/settings/", body, format="json")
            self.assertEqual(response.status_code, 400)
        response = self.client.put("/api/v1/settings/", {"asuswrt_password": "", "asuswrt_verify_ssl": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.asuswrt_password, "router-secret")

    def test_viewers_cannot_test_or_sync_router(self):
        user = User.objects.create_user("viewer", password="password")
        self.client.force_authenticate(user)
        for endpoint in ("test", "sync"):
            response = self.client.post(f"/api/v1/integrations/asuswrt/{endpoint}/", {}, format="json")
            self.assertEqual(response.status_code, 403)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_missing_clients_do_not_delete_devices_or_change_presence(self, inspect):
        device = Device.objects.create(mac=MAC, ip=IP, online=True)
        inspect.return_value = parse_clients({"get_clientlist": {}})
        sync_asuswrt()
        device.refresh_from_db()
        self.assertTrue(device.online)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_archived_devices_are_not_enriched(self, inspect):
        device = Device.objects.create(mac=MAC, ip=IP, archived=True)
        inspect.return_value = self.parsed()
        sync_asuswrt()
        device.refresh_from_db()
        self.assertEqual(device.asuswrt_data, {})

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_merged_interface_is_enriched_without_creating_another_logical_device(self, inspect):
        root = Device.objects.create(mac="aa:bb:cc:dd:ee:20", ip="192.168.50.20", known=True)
        interface = Device.objects.create(mac=MAC, ip=IP, merged_into=root)
        self.config.asuswrt_create_devices = True
        self.config.save()
        inspect.return_value = self.parsed()
        self.assertEqual(sync_asuswrt()["devices_discovered"], 0)
        interface.refresh_from_db()
        self.assertEqual(interface.merged_into_id, root.pk)
        self.assertTrue(interface.asuswrt_data)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_newer_ip_observation_wins(self, inspect):
        device = Device.objects.create(mac=MAC, ip="192.168.50.99", lastseen=timezone.now() + timedelta(minutes=1))
        inspect.return_value = self.parsed()
        sync_asuswrt()
        device.refresh_from_db()
        self.assertEqual(device.ip, "192.168.50.99")
        self.assertEqual(device.asuswrt_data, {})

    def test_saving_new_password_resets_authentication_pause(self):
        self.config.asuswrt_auth_failed = True
        self.config.save()
        response = self.client.put("/api/v1/settings/", {"asuswrt_password": "new-secret"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertFalse(self.config.asuswrt_auth_failed)

    @patch("core.integrations.asuswrt.inspect_asuswrt")
    def test_manual_sync_endpoint_enriches_without_revealing_secrets(self, inspect):
        inspect.return_value = self.parsed()
        response = self.client.post("/api/v1/integrations/asuswrt/sync/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["status"], "ok")
        self.assertNotIn("router-secret", json.dumps(response.data))
