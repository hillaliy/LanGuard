from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from .models import AppSettings, Device, UserAccess
from .wake_on_lan import magic_packet, send_magic_packet, wake_broadcast_address


class WakeOnLanPacketTests(SimpleTestCase):
    def test_magic_packet_contains_header_and_repeated_mac(self):
        packet = magic_packet("00:11:22:33:44:55")

        self.assertEqual(packet, b"\xff" * 6 + bytes.fromhex("001122334455") * 16)

    def test_magic_packet_rejects_invalid_mac(self):
        with self.assertRaisesRegex(ValueError, "valid MAC"):
            magic_packet("not-a-mac")

    def test_broadcast_uses_most_specific_matching_range(self):
        result = wake_broadcast_address(
            "192.168.1.20",
            ["192.168.0.0/16", "192.168.1.0/24"],
        )

        self.assertEqual(result, "192.168.1.255")

    def test_broadcast_falls_back_when_device_is_outside_configured_ranges(self):
        result = wake_broadcast_address("192.168.50.20", ["192.168.1.0/24"])

        self.assertEqual(result, "255.255.255.255")

    @patch("core.wake_on_lan.socket.socket")
    def test_send_magic_packet_sends_three_udp_broadcasts(self, socket_mock):
        wake_socket = socket_mock.return_value.__enter__.return_value

        send_magic_packet("00:11:22:33:44:55", "192.168.1.255")

        wake_socket.setsockopt.assert_called_once()
        self.assertEqual(wake_socket.sendto.call_count, 3)
        wake_socket.sendto.assert_called_with(
            b"\xff" * 6 + bytes.fromhex("001122334455") * 16,
            ("192.168.1.255", 9),
        )


class WakeDeviceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(
            name="Desktop",
            ip="192.168.1.20",
            mac="00:11:22:33:44:55",
        )
        AppSettings.objects.create(
            ip_range="192.168.1.0/24",
            scan_ranges=["192.168.1.0/24"],
        )

    @patch("core.views.send_magic_packet")
    def test_wake_device_sends_packet_to_network_broadcast(self, send_mock):
        response = self.client.post(
            "/api/v1/device/wake/",
            {"id": self.device.id},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        send_mock.assert_called_once_with("00:11:22:33:44:55", "192.168.1.255")
        self.assertEqual(response.data["notification"]["title"], "Wake request sent")

    def test_wake_device_requires_authentication(self):
        client = APIClient()

        response = client.post(
            "/api/v1/device/wake/",
            {"id": self.device.id},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_wake_device_requires_scan_permission(self):
        viewer = User.objects.create_user(username="viewer", password="password")
        UserAccess.objects.create(user=viewer, can_run_scans=False)
        client = APIClient()
        client.force_authenticate(viewer)

        response = client.post(
            "/api/v1/device/wake/",
            {"id": self.device.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_wake_device_rejects_invalid_mac(self):
        self.device.mac = "invalid"
        self.device.save(update_fields=["mac"])

        response = self.client.post(
            "/api/v1/device/wake/",
            {"id": self.device.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid MAC", response.data["device"])

    @patch("core.views.send_magic_packet", side_effect=OSError("network unavailable"))
    def test_wake_device_returns_safe_error_when_send_fails(self, _send_mock):
        response = self.client.post(
            "/api/v1/device/wake/",
            {"id": self.device.id},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["notification"]["title"], "Wake request failed")
        self.assertNotIn("network unavailable", str(response.data))

    @patch("core.views.send_magic_packet")
    def test_wake_device_does_not_wake_archived_devices(self, send_mock):
        self.device.archived = True
        self.device.save(update_fields=["archived"])

        response = self.client.post(
            "/api/v1/device/wake/",
            {"id": self.device.id},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        send_mock.assert_not_called()
