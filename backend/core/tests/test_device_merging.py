from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import AppSettings, Device, DevicePort, NetworkEvent
from ..scanning.events import create_event
from ..views.devices import device_availability_payload


class DeviceMergingApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.primary = Device.objects.create(
            name="Workstation",
            ip="192.168.1.20",
            mac="00:11:22:33:44:55",
            online=False,
            status=Device.Status.OFFLINE,
        )
        self.secondary = Device.objects.create(
            name="Workstation Wi-Fi",
            hostname="workstation-wifi",
            ip="192.168.1.21",
            mac="00:11:22:33:44:66",
            online=True,
            status=Device.Status.ONLINE,
        )
        AppSettings.objects.create(
            ip_range="192.168.1.0/24",
            scan_ranges=["192.168.1.0/24"],
        )

    def merge(self):
        return self.client.post(
            "/api/v1/device/merge/",
            {
                "target_id": self.primary.id,
                "source_ids": [self.secondary.id],
            },
            format="json",
        )

    def test_merge_keeps_interfaces_and_hides_secondary_inventory_row(self):
        DevicePort.objects.create(
            device=self.secondary,
            port=443,
            protocol="tcp",
            open=True,
        )

        response = self.merge()

        self.assertEqual(response.status_code, 200)
        self.secondary.refresh_from_db()
        self.assertEqual(self.secondary.merged_into_id, self.primary.id)
        self.assertEqual(self.secondary.merged_by_id, self.user.id)
        inventory = self.client.get("/api/v1/device/").data
        self.assertEqual(inventory["pagination"]["count"], 1)
        self.assertEqual(inventory["data"][0]["id"], self.primary.id)
        self.assertTrue(inventory["data"][0]["online"])
        self.assertEqual(inventory["data"][0]["status"], Device.Status.ONLINE)
        self.assertEqual(inventory["data"][0]["interface_count"], 2)
        self.assertEqual(inventory["counters"]["all_devices"], 1)

        detail = self.client.get(
            "/api/v1/device/",
            {"id": self.primary.id},
        ).data["data"]
        self.assertEqual(len(detail["interfaces"]), 2)
        self.assertEqual(
            {item["mac"] for item in detail["interfaces"]},
            {self.primary.mac, self.secondary.mac},
        )
        self.assertEqual(detail["open_ports"][0]["port"], 443)

    def test_secondary_search_and_online_filter_return_primary_device(self):
        self.merge()

        search_response = self.client.get(
            "/api/v1/device/",
            {"search": "workstation-wifi"},
        )
        online_response = self.client.get(
            "/api/v1/device/",
            {"status": Device.Status.ONLINE},
        )

        self.assertEqual(search_response.data["data"][0]["id"], self.primary.id)
        self.assertEqual(online_response.data["data"][0]["id"], self.primary.id)

    def test_detail_request_for_secondary_resolves_to_primary_device(self):
        self.merge()

        response = self.client.get(
            "/api/v1/device/",
            {"id": self.secondary.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.primary.id)

    def test_unmerge_restores_separate_inventory_row_and_history(self):
        event = NetworkEvent.objects.create(
            device=self.secondary,
            event_type=NetworkEvent.EventType.IP_CHANGED,
            message="Wi-Fi IP changed",
        )
        self.merge()

        merged_history = self.client.get(
            "/api/v1/events/",
            {"device": self.primary.id},
        ).data["data"]
        self.assertIn(event.id, {item["id"] for item in merged_history})

        response = self.client.post(
            "/api/v1/device/unmerge/",
            {
                "target_id": self.primary.id,
                "interface_id": self.secondary.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.secondary.refresh_from_db()
        self.assertIsNone(self.secondary.merged_into_id)
        self.assertIsNone(self.secondary.merged_at)
        self.assertEqual(
            self.client.get("/api/v1/device/").data["pagination"]["count"],
            2,
        )
        self.assertTrue(NetworkEvent.objects.filter(id=event.id).exists())

    def test_primary_cannot_be_deleted_until_interfaces_are_separated(self):
        self.merge()

        response = self.client.delete(
            f"/api/v1/device/?id={self.primary.id}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Device.objects.filter(id=self.primary.id).exists())

    def test_archive_and_restore_apply_to_every_interface(self):
        self.merge()

        archive_response = self.client.put(
            f"/api/v1/device/?id={self.primary.id}",
            {"archived": True},
            format="json",
        )
        self.assertEqual(archive_response.status_code, 202)
        self.primary.refresh_from_db()
        self.secondary.refresh_from_db()
        self.assertTrue(self.primary.archived)
        self.assertTrue(self.secondary.archived)

        restore_response = self.client.put(
            f"/api/v1/device/?id={self.primary.id}",
            {"archived": False},
            format="json",
        )
        self.assertEqual(restore_response.status_code, 202)
        self.primary.refresh_from_db()
        self.secondary.refresh_from_db()
        self.assertFalse(self.primary.archived)
        self.assertFalse(self.secondary.archived)

    def test_merge_candidates_exclude_already_merged_interfaces(self):
        third = Device.objects.create(
            name="Another device",
            ip="192.168.1.22",
            mac="00:11:22:33:44:77",
        )
        self.merge()

        response = self.client.get(
            "/api/v1/device/merge-candidates/",
            {"id": self.primary.id},
        )

        candidate_ids = {item["id"] for item in response.data["data"]}
        self.assertNotIn(self.secondary.id, candidate_ids)
        self.assertIn(third.id, candidate_ids)

    def test_inventory_export_and_import_preserve_interface_group(self):
        self.merge()
        exported = self.client.get("/api/v1/devices/export/").json()
        secondary_payload = next(
            item for item in exported["devices"] if item["mac"] == self.secondary.mac
        )
        self.assertEqual(secondary_payload["merged_into_mac"], self.primary.mac)

        Device.objects.filter(pk=self.secondary.id).update(
            merged_into=None,
            merged_at=None,
            merged_by=None,
        )
        Device.objects.all().delete()
        response = self.client.post(
            "/api/v1/devices/import/",
            exported,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        restored_primary = Device.objects.get(mac=self.primary.mac)
        restored_secondary = Device.objects.get(mac=self.secondary.mac)
        self.assertEqual(restored_secondary.merged_into_id, restored_primary.id)

    @patch("core.views.devices.send_magic_packet")
    def test_wake_sends_packet_to_every_interface(self, send_mock):
        self.merge()

        response = self.client.post(
            "/api/v1/device/wake/",
            {"id": self.primary.id},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["data"]["interfaces"], 2)
        self.assertEqual(send_mock.call_count, 2)
        send_mock.assert_any_call(self.primary.mac, "192.168.1.255")
        send_mock.assert_any_call(self.secondary.mac, "192.168.1.255")


class MergedDevicePresenceTests(TestCase):
    def setUp(self):
        self.primary = Device.objects.create(
            name="Laptop",
            ip="192.168.1.30",
            mac="00:aa:bb:cc:dd:01",
            known=True,
            online=True,
        )
        self.secondary = Device.objects.create(
            name="Laptop Ethernet",
            ip="192.168.1.31",
            mac="00:aa:bb:cc:dd:02",
            online=False,
            merged_into=self.primary,
        )

    @patch("core.scanning.events.notify_event")
    def test_interface_transition_does_not_notify_while_another_is_online(
        self,
        notify_mock,
    ):
        event = create_event(
            NetworkEvent.EventType.DEVICE_OFFLINE,
            device=self.secondary,
            message="Laptop Ethernet went offline",
        )

        notify_mock.assert_not_called()
        self.assertTrue(event.notified)
        self.assertEqual(
            event.metadata["notification_skipped"],
            "other_interface_online",
        )
        self.assertEqual(event.device_id, self.secondary.id)

    @patch("core.scanning.events.notify_event")
    def test_group_transition_uses_primary_profile_for_notification(self, notify_mock):
        self.primary.online = False
        self.primary.status = Device.Status.OFFLINE
        self.primary.save(update_fields=["online", "status"])
        self.secondary.online = True
        self.secondary.status = Device.Status.ONLINE
        self.secondary.save(update_fields=["online", "status"])

        event = create_event(
            NetworkEvent.EventType.DEVICE_ONLINE,
            device=self.secondary,
            message="Laptop Ethernet came online",
        )

        self.assertEqual(event.device_id, self.primary.id)
        self.assertEqual(event.message, "Laptop came online")
        self.assertEqual(event.metadata["interface_device_id"], self.secondary.id)
        notify_mock.assert_called_once_with(event)

    def test_availability_uses_interface_metadata_on_group_events(self):
        now = timezone.now()
        before_period = now - timedelta(days=2)
        NetworkEvent.objects.create(
            device=self.primary,
            event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            message="Laptop went offline",
            metadata={"interface_device_id": self.primary.id},
            created_at=before_period,
        )
        NetworkEvent.objects.create(
            device=self.primary,
            event_type=NetworkEvent.EventType.DEVICE_ONLINE,
            message="Laptop came online",
            metadata={"interface_device_id": self.secondary.id},
            created_at=before_period + timedelta(minutes=1),
        )
        NetworkEvent.objects.create(
            device=self.primary,
            event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            message="Laptop went offline",
            metadata={"interface_device_id": self.secondary.id},
            created_at=now - timedelta(hours=12),
        )

        payload = device_availability_payload(self.primary, "day", now=now)

        self.assertEqual(payload["status_changes"], 1)
        self.assertAlmostEqual(payload["availability_percent"], 50.0, places=1)
