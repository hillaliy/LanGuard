from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import Device, DeviceRelatedLink, UserAccess


class DeviceRelatedLinkApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.device = Device.objects.create(
            name="Router",
            ip="192.168.1.1",
            mac="aa:bb:cc:dd:ee:01",
        )

    def test_device_detail_includes_ordered_related_links(self):
        second = DeviceRelatedLink.objects.create(
            device=self.device,
            label="Invoice",
            url="https://documents.example/invoice.pdf",
            position=1,
        )
        first = DeviceRelatedLink.objects.create(
            device=self.device,
            label="Manual",
            url="https://documents.example/manual.pdf",
            position=0,
        )

        response = self.client.get("/api/v1/device/", {"id": self.device.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [link["id"] for link in response.data["data"]["related_links"]],
            [first.id, second.id],
        )

    def test_related_link_crud_and_reordering(self):
        manual_response = self.client.post(
            f"/api/v1/device/links/?id={self.device.id}",
            {"label": "Manual", "url": "https://documents.example/manual.pdf"},
            format="json",
        )
        invoice_response = self.client.post(
            f"/api/v1/device/links/?id={self.device.id}",
            {"label": "Invoice", "url": "https://documents.example/invoice.pdf"},
            format="json",
        )
        self.assertEqual(manual_response.status_code, 201)
        self.assertEqual(invoice_response.status_code, 201)
        manual_id = manual_response.data["data"][0]["id"]
        invoice_id = invoice_response.data["data"][1]["id"]

        update_response = self.client.put(
            f"/api/v1/device/links/?id={self.device.id}&link_id={manual_id}",
            {"label": "Setup guide"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["data"][0]["label"], "Setup guide")

        reorder_response = self.client.patch(
            f"/api/v1/device/links/?id={self.device.id}",
            {"order": [invoice_id, manual_id]},
            format="json",
        )
        self.assertEqual(reorder_response.status_code, 200)
        self.assertEqual(
            [link["id"] for link in reorder_response.data["data"]],
            [invoice_id, manual_id],
        )

        delete_response = self.client.delete(
            f"/api/v1/device/links/?id={self.device.id}&link_id={invoice_id}"
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual([link["id"] for link in delete_response.data["data"]], [manual_id])
        self.assertEqual(DeviceRelatedLink.objects.get(pk=manual_id).position, 0)

    def test_related_links_reject_unsafe_and_duplicate_urls(self):
        endpoint = f"/api/v1/device/links/?id={self.device.id}"
        invalid_scheme = self.client.post(
            endpoint,
            {"label": "Unsafe", "url": "javascript:alert(1)"},
            format="json",
        )
        credentials = self.client.post(
            endpoint,
            {"label": "Private", "url": "https://admin:secret@example.com/manual"},
            format="json",
        )
        created = self.client.post(
            endpoint,
            {"label": "Manual", "url": "https://documents.example/manual.pdf"},
            format="json",
        )
        duplicate = self.client.post(
            endpoint,
            {"label": "Same manual", "url": "https://documents.example/manual.pdf"},
            format="json",
        )

        self.assertEqual(invalid_scheme.status_code, 400)
        self.assertEqual(credentials.status_code, 400)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(DeviceRelatedLink.objects.count(), 1)

    def test_related_link_writes_require_device_edit_permission(self):
        viewer = User.objects.create_user(username="viewer", password="password")
        UserAccess.objects.create(user=viewer, can_edit_devices=False)
        viewer_client = APIClient()
        viewer_client.force_authenticate(viewer)
        endpoint = f"/api/v1/device/links/?id={self.device.id}"

        read_response = viewer_client.get(endpoint)
        write_response = viewer_client.post(
            endpoint,
            {"label": "Manual", "url": "https://documents.example/manual.pdf"},
            format="json",
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(write_response.status_code, 403)

    def test_related_link_cannot_be_modified_through_another_device(self):
        other_device = Device.objects.create(
            name="Camera",
            ip="192.168.1.2",
            mac="aa:bb:cc:dd:ee:02",
        )
        link = DeviceRelatedLink.objects.create(
            device=other_device,
            label="Manual",
            url="https://documents.example/camera.pdf",
        )

        response = self.client.put(
            f"/api/v1/device/links/?id={self.device.id}&link_id={link.id}",
            {"label": "Changed"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        link.refresh_from_db()
        self.assertEqual(link.label, "Manual")
