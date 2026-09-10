from unittest.mock import Mock, patch
from uuid import UUID

import requests
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .homebox import HomeBoxClient, HomeBoxError
from .models import AppSettings, Device, UserAccess
from .serializers import AppSettingsSerializer, DeviceSerializer
from .views import import_inventory_devices


ITEM_ID = "39e038fb-a217-4528-b138-162291b36aca"


class HomeBoxTests(TestCase):
    def setUp(self):
        self.config = AppSettings.load()
        self.config.homebox_enabled = True
        self.config.homebox_url = "https://homebox.example"
        self.config.homebox_api_token = "secret-key"
        self.config.save()
        self.user = User.objects.create_user("homebox-admin", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(mac="00:11:22:33:44:55", ip="192.168.0.10")

    def response(self, payload, status=200):
        return Mock(status_code=status, json=Mock(return_value=payload))

    def test_settings_hide_and_preserve_token(self):
        self.assertNotIn("homebox_api_token", AppSettingsSerializer(self.config).data)
        serializer = AppSettingsSerializer(self.config, data={"homebox_api_token": ""}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.config.refresh_from_db()
        self.assertEqual(self.config.homebox_api_token, "secret-key")
        self.assertTrue(serializer.data["homebox_configured"])

    def test_url_change_requires_new_key(self):
        serializer = AppSettingsSerializer(self.config, data={"homebox_url": "https://other.example"}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("homebox_api_token", serializer.errors)

    @patch("core.homebox.requests.get")
    def test_search_and_pagination(self, get):
        get.return_value = self.response({"items": [
            {"id": ITEM_ID, "name": "Router", "assetId": "NET-0042"},
        ]})
        response = self.client.get("/api/v1/integrations/homebox/items/", {"q": "Router", "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["items"], [
            {"value": ITEM_ID, "label": "NET-0042 · Router"},
        ])
        self.assertEqual(get.call_args.kwargs["params"], {"q": "Router", "page": 2, "pageSize": 25})
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer secret-key")

    @patch("core.homebox.requests.get")
    def test_search_uses_name_when_asset_id_is_missing(self, get):
        get.return_value = self.response({"items": [{"id": ITEM_ID, "name": "Router"}]})
        response = self.client.get("/api/v1/integrations/homebox/items/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["items"], [{"value": ITEM_ID, "label": "Router"}])

    @patch("core.homebox.requests.get")
    def test_connection_uses_saved_key(self, get):
        get.return_value = self.response({"items": []})
        response = self.client.post("/api/v1/integrations/homebox/test/", {"url": self.config.homebox_url}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret-key", str(response.data))

    @patch("core.homebox.requests.get")
    def test_different_host_does_not_receive_saved_key(self, get):
        response = self.client.post("/api/v1/integrations/homebox/test/", {"url": "https://other.example"}, format="json")
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    @patch("core.homebox.requests.get")
    def test_link_validate_and_unlink(self, get):
        get.return_value = self.response({"id": ITEM_ID, "name": "Router"})
        serializer = DeviceSerializer(self.device, data={"homebox_item_id": ITEM_ID}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(serializer.data["homebox_link"], f"https://homebox.example/item/{ITEM_ID}")
        get.reset_mock()
        serializer = DeviceSerializer(self.device, data={"homebox_item_id": None}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(serializer.data["homebox_link"], "")
        get.assert_not_called()

    @patch("core.homebox.requests.get")
    def test_missing_item_rejected_but_existing_link_can_be_saved_offline(self, get):
        get.return_value = self.response({}, 404)
        serializer = DeviceSerializer(self.device, data={"homebox_item_id": ITEM_ID}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.device.homebox_item_id = UUID(ITEM_ID)
        self.device.save()
        get.reset_mock()
        serializer = DeviceSerializer(self.device, data={"homebox_item_id": ITEM_ID, "name": "Changed"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        get.assert_not_called()

    def test_disabled_integration_hides_link(self):
        self.device.homebox_item_id = UUID(ITEM_ID)
        self.config.homebox_enabled = False
        self.config.save()
        self.assertFalse(DeviceSerializer(self.device).data["homebox_available"])
        self.assertEqual(DeviceSerializer(self.device).data["homebox_link"], "")
        self.assertEqual(self.client.get("/api/v1/integrations/homebox/items/").status_code, 400)

    def test_device_list_filters_by_homebox_link(self):
        linked = Device.objects.create(
            mac="00:11:22:33:44:66",
            ip="192.168.0.11",
            homebox_item_id=UUID(ITEM_ID),
        )

        linked_response = self.client.get("/api/v1/device/", {"homebox_linked": "true"})
        unlinked_response = self.client.get("/api/v1/device/", {"homebox_linked": "false"})
        invalid_response = self.client.get("/api/v1/device/", {"homebox_linked": "invalid"})

        self.assertEqual(linked_response.status_code, 200)
        self.assertEqual([item["id"] for item in linked_response.data["data"]], [linked.id])
        self.assertEqual(unlinked_response.status_code, 200)
        self.assertEqual([item["id"] for item in unlinked_response.data["data"]], [self.device.id])
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("homebox_linked", invalid_response.data)

    def test_scan_status_exposes_safe_homebox_state(self):
        response = self.client.get("/api/v1/scan/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["integrations"]["homebox"],
            {"enabled": True, "configured": True},
        )
        self.assertNotIn("homebox.example", str(response.data))
        self.assertNotIn("secret-key", str(response.data))

    @patch("core.homebox.requests.get")
    def test_access_control(self, get):
        user = User.objects.create_user("homebox-reader")
        UserAccess.objects.create(user=user, can_edit_devices=False)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get("/api/v1/integrations/homebox/items/").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/integrations/homebox/test/", {}).status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get("/api/v1/integrations/homebox/items/").status_code, (401, 403))
        get.assert_not_called()

    @patch("core.homebox.requests.get")
    def test_failures_are_sanitized(self, get):
        for response in (self.response({}, 401), self.response({}, 302), self.response([]), self.response({"items": "bad"})):
            get.return_value = response
            result = self.client.get("/api/v1/integrations/homebox/items/")
            self.assertEqual(result.status_code, 502)
            self.assertNotIn("secret-key", str(result.data))
        get.side_effect = requests.Timeout("secret-key")
        self.assertEqual(self.client.get("/api/v1/integrations/homebox/items/").status_code, 502)

    def test_invalid_urls_and_ids(self):
        for url in ("file:///tmp/test", "https://user:pass@example.com", "https://example.com?q=x", "http://[invalid", "http://example.com:bad"):
            with self.assertRaises(HomeBoxError):
                HomeBoxClient(url, "key")
        serializer = DeviceSerializer(self.device, data={"homebox_item_id": "../bad"}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(self.client.get("/api/v1/integrations/homebox/items/", {"page": -1}).status_code, 400)

    def test_inventory_preserves_link(self):
        self.device.homebox_item_id = UUID(ITEM_ID)
        self.device.save()
        response = self.client.get("/api/v1/devices/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(ITEM_ID, str(response.json()))
        self.device.homebox_item_id = None
        self.device.save()
        import_inventory_devices(response.json())
        self.device.refresh_from_db()
        self.assertEqual(self.device.homebox_item_id, UUID(ITEM_ID))
