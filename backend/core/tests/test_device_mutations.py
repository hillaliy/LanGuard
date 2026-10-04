from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import (
    Device,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)

class DeviceMutationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(
            name="Laptop",
            ip="192.168.1.20",
            mac="aa:aa:aa:aa:aa:aa",
        )
        self.scan_run = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.SUCCESS,
            devices_seen=1,
            online_devices=1,
        )
        self.event = NetworkEvent.objects.create(
            scan_run=self.scan_run,
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Laptop came online",
        )
        self.delivery = NotificationDelivery.objects.create(
            event=self.event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.FAILED,
            attempts=1,
        )

    def test_bulk_update_marks_selected_devices_as_known(self):
        second_device = Device.objects.create(
            name="Phone",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
            known=False,
        )
        untouched_device = Device.objects.create(
            name="Tablet",
            ip="192.168.1.22",
            mac="cc:cc:cc:cc:cc:cc",
            known=False,
        )
        self.device.known = False
        self.device.save(update_fields=["known"])

        response = self.client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id, second_device.id], "known": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        second_device.refresh_from_db()
        untouched_device.refresh_from_db()
        self.assertTrue(self.device.known)
        self.assertTrue(second_device.known)
        self.assertFalse(untouched_device.known)
        self.assertEqual(response.data["data"]["updated_count"], 2)
        self.assertEqual(
            response.data["notification"]["message"],
            "2 selected devices marked as known.",
        )

    def test_bulk_update_marks_visitors_and_marking_known_clears_visitor(self):
        response = self.client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id], "is_visitor": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertTrue(self.device.known)
        self.assertTrue(self.device.is_visitor)
        self.assertEqual(
            response.data["notification"]["message"],
            "1 selected device marked as visitor.",
        )

        response = self.client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id], "known": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertTrue(self.device.known)
        self.assertFalse(self.device.is_visitor)

    def test_bulk_update_reviews_known_devices_and_skips_unknown_devices(self):
        self.device.known = True
        self.device.vendor = "Linux"
        self.device.save(update_fields=["known", "vendor"])
        DevicePort.objects.create(device=self.device, port=3389, protocol="tcp", open=True)
        unknown_device = Device.objects.create(
            name="Unknown phone",
            ip="192.168.1.21",
            mac="bb:bb:bb:bb:bb:bb",
            known=False,
        )

        response = self.client.post(
            "/api/v1/devices/bulk-update/",
            {
                "ids": [self.device.id, unknown_device.id],
                "acknowledge_attention": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        unknown_device.refresh_from_db()
        self.assertTrue(self.device.attention_acknowledged_signature)
        self.assertEqual(unknown_device.attention_acknowledged_signature, "")
        self.assertEqual(response.data["data"]["reviewed_count"], 1)
        self.assertEqual(response.data["data"]["skipped_unknown_count"], 1)
        self.assertIn("mark them as known first", response.data["notification"]["message"])
        reviewed = self.client.get(
            "/api/v1/device/", {"id": self.device.id}
        ).data["data"]
        unknown = self.client.get(
            "/api/v1/device/", {"id": unknown_device.id}
        ).data["data"]
        self.assertFalse(reviewed["needs_attention"])
        self.assertTrue(unknown["needs_attention"])

    def test_device_visitor_classification_enforces_known_invariant(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"is_visitor": True},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.device.refresh_from_db()
        self.assertTrue(self.device.known)
        self.assertTrue(self.device.is_visitor)

        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"known": False},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.device.refresh_from_db()
        self.assertFalse(self.device.known)
        self.assertFalse(self.device.is_visitor)

    def test_device_rejects_unknown_visitor_state(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"known": False, "is_visitor": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("is_visitor", response.data["info"])

    def test_bulk_update_rejects_missing_device(self):
        response = self.client.post(
            "/api/v1/devices/bulk-update/",
            {"ids": [self.device.id, 999999], "known": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ids", response.data)

    def test_device_can_save_external_link(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"external_url": "https://192.168.1.10:8443"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.device.refresh_from_db()
        self.assertEqual(self.device.external_url, "https://192.168.1.10:8443")
        self.assertFalse(self.device.external_url_follow_device_ip)

    def test_device_external_link_can_follow_current_ipv4(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {
                "external_url": "http://192.168.1.10:8080/admin?tab=status#network",
                "external_url_follow_device_ip": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        device = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertEqual(
            device["effective_external_url"],
            "http://192.168.1.20:8080/admin?tab=status#network",
        )

        self.device.ip = "192.168.1.35"
        self.device.save(update_fields=["ip"])
        device = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertEqual(
            device["effective_external_url"],
            "http://192.168.1.35:8080/admin?tab=status#network",
        )

    def test_fixed_external_link_does_not_follow_device_ip(self):
        self.device.external_url = "https://device.example.test/admin"
        self.device.save(update_fields=["external_url"])

        device = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]

        self.assertFalse(device["external_url_follow_device_ip"])
        self.assertEqual(device["effective_external_url"], "https://device.example.test/admin")

    def test_device_can_save_presence_notification_preferences(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {
                "online_notification_preference": Device.NotificationPreference.ALWAYS,
                "offline_notification_preference": Device.NotificationPreference.NEVER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.device.refresh_from_db()
        self.assertEqual(
            self.device.online_notification_preference,
            Device.NotificationPreference.ALWAYS,
        )
        self.assertEqual(
            self.device.offline_notification_preference,
            Device.NotificationPreference.NEVER,
        )

    def test_device_rejects_invalid_notification_preference(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"online_notification_preference": "sometimes"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("online_notification_preference", response.data["info"])

    def test_device_can_save_custom_presence_expectation(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {
                "presence_expectation": Device.PresenceExpectation.OCCASIONAL,
                "offline_attention_after_days": 14,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.device.refresh_from_db()
        self.assertEqual(
            self.device.presence_expectation,
            Device.PresenceExpectation.OCCASIONAL,
        )
        self.assertEqual(self.device.offline_attention_after_days, 14)

    def test_device_rejects_non_http_external_link(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"external_url": "javascript:alert(1)"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("external_url", response.data["info"])

    def test_device_rejects_external_link_with_embedded_credentials(self):
        response = self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"external_url": "https://admin:secret@192.168.1.20/"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("external_url", response.data["info"])

    @patch("core.views.devices.detect_web_interface", return_value="http://192.168.1.10")
    def test_device_web_interface_endpoint_probes_saved_device(self, detect):
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)

        response = self.client.get(
            "/api/v1/device/web-interface/",
            {"id": self.device.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "http://192.168.1.10")
        detect.assert_called_once_with("192.168.1.20", [80])
