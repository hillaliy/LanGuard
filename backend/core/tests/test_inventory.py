from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import (
    Device,
    DeviceIPAddressAssignment,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)
from ..views.inventory import parse_inventory_datetime

class InventoryApiTests(TestCase):
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

    def test_device_inventory_export_requires_admin(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/devices/export/")

        self.assertEqual(response.status_code, 403)

    def test_device_inventory_export_returns_shared_format(self):
        self.device.known = True
        self.device.is_visitor = True
        self.device.icon = "temperature-humidity-sensor"
        self.device.comments = "Demo note"
        self.device.external_url = "https://192.168.1.10"
        self.device.external_url_follow_device_ip = True
        self.device.online_notification_preference = Device.NotificationPreference.ALWAYS
        self.device.offline_notification_preference = Device.NotificationPreference.NEVER
        self.device.presence_expectation = Device.PresenceExpectation.OCCASIONAL
        self.device.offline_attention_after_days = 14
        self.device.save(
            update_fields=[
                "known",
                "is_visitor",
                "icon",
                "comments",
                "external_url",
                "external_url_follow_device_ip",
                "online_notification_preference",
                "offline_notification_preference",
                "presence_expectation",
                "offline_attention_after_days",
            ]
        )
        DevicePort.objects.create(device=self.device, port=80, protocol="tcp", open=True)
        self.client.put(
            f"/api/v1/device/?id={self.device.id}",
            {"acknowledge_attention": True},
            format="json",
        )

        response = self.client.get("/api/v1/devices/export/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["format"], "languard-device-inventory")
        exported_device = response.json()["devices"][0]
        self.assertEqual(exported_device["name"], "Laptop")
        self.assertEqual(exported_device["mac"], "aa:aa:aa:aa:aa:aa")
        self.assertEqual(exported_device["icon"], "humidity")
        self.assertEqual(exported_device["open_ports"], [80])
        self.assertEqual(exported_device["comments"], "Demo note")
        self.assertEqual(exported_device["external_url"], "https://192.168.1.10")
        self.assertTrue(exported_device["external_url_follow_device_ip"])
        self.assertEqual(exported_device["online_notification_preference"], "always")
        self.assertEqual(exported_device["offline_notification_preference"], "never")
        self.assertEqual(exported_device["presence_expectation"], "occasional")
        self.assertEqual(exported_device["offline_attention_after_days"], 14)
        self.assertTrue(exported_device["is_visitor"])
        self.assertTrue(exported_device["attention_acknowledged"])
        self.assertTrue(exported_device["first_seen"].endswith("Z"))

    def test_device_inventory_import_updates_existing_device_by_mac(self):
        self.device.firstseen = timezone.now() - timedelta(days=1)
        self.device.save(update_fields=["firstseen"])

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Living Room TV",
                        "ip": "192.168.1.50",
                        "mac": "aa:aa:aa:aa:aa:aa",
                        "vendor": "Apple",
                        "icon": "tv",
                        "known": True,
                        "is_gateway": False,
                        "status": Device.Status.ONLINE,
                        "open_ports": [80, "443"],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["created"], 0)
        self.assertEqual(response.data["data"]["updated"], 1)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Living Room TV")
        self.assertEqual(self.device.ip, "192.168.1.50")
        self.assertEqual(self.device.vendor, "Apple")
        self.assertEqual(self.device.icon, "tv")
        self.assertTrue(self.device.known)
        self.assertTrue(
            self.device.ip_assignments.filter(
                ip="192.168.1.20",
                valid_until__isnull=False,
            ).exists()
        )
        self.assertTrue(
            self.device.ip_assignments.filter(
                ip="192.168.1.50",
                valid_until__isnull=True,
            ).exists()
        )
        self.assertEqual(
            list(self.device.ports.filter(open=True).values_list("port", flat=True)),
            [80, 443],
        )

    def test_legacy_inventory_import_preserves_existing_visitor_classification(self):
        self.device.known = True
        self.device.is_visitor = True
        self.device.save(update_fields=["known", "is_visitor"])

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Visiting phone",
                        "ip": self.device.ip,
                        "mac": self.device.mac,
                        "known": True,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertTrue(self.device.known)
        self.assertTrue(self.device.is_visitor)

    def test_device_inventory_import_restores_notification_preferences(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Laptop",
                        "ip": self.device.ip,
                        "mac": self.device.mac,
                        "online_notification_preference": "always",
                        "offline_notification_preference": "never",
                        "presence_expectation": "occasional",
                        "offline_attention_after_days": 14,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.online_notification_preference, "always")
        self.assertEqual(self.device.offline_notification_preference, "never")
        self.assertEqual(self.device.presence_expectation, "occasional")
        self.assertEqual(self.device.offline_attention_after_days, 14)

    def test_device_inventory_import_preserves_notification_preferences_when_missing(self):
        self.device.online_notification_preference = Device.NotificationPreference.ALWAYS
        self.device.offline_notification_preference = Device.NotificationPreference.NEVER
        self.device.save(
            update_fields=[
                "online_notification_preference",
                "offline_notification_preference",
            ]
        )

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Laptop",
                        "ip": self.device.ip,
                        "mac": self.device.mac,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.online_notification_preference, "always")
        self.assertEqual(self.device.offline_notification_preference, "never")

    def test_watchyourlan_inventory_import_maps_api_all_hosts(self):
        response = self.client.post(
            "/api/v1/devices/import/watchyourlan/",
            [
                {
                    "ID": 7,
                    "Name": "Living Room TV",
                    "DNS": "living-room-tv.local",
                    "Iface": "eth0",
                    "IP": "192.168.1.50",
                    "Mac": "b0:be:76:12:34:56",
                    "Hw": "TP-Link Systems Inc.",
                    "Date": "2026-08-29 10:30:00",
                    "Known": 1,
                    "Now": 1,
                },
                {
                    "ID": 8,
                    "Name": "Offline tablet",
                    "DNS": "",
                    "Iface": "eth0",
                    "IP": "192.168.1.51",
                    "Mac": "90:dd:5d:12:34:56",
                    "Hw": "Apple, Inc.",
                    "Date": "2026-08-29 09:15:00",
                    "Known": 0,
                    "Now": 0,
                },
            ],
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["created"], 2)
        imported = Device.objects.get(mac="b0:be:76:12:34:56")
        self.assertEqual(imported.name, "Living Room TV")
        self.assertEqual(imported.hostname, "living-room-tv.local")
        self.assertEqual(imported.hostname_source, Device.IdentitySource.IMPORTED)
        self.assertEqual(imported.vendor, "TP-Link Systems Inc.")
        self.assertEqual(imported.vendor_source, Device.IdentitySource.IMPORTED)
        self.assertTrue(imported.known)
        self.assertTrue(imported.online)
        self.assertEqual(imported.status, Device.Status.ONLINE)
        offline = Device.objects.get(mac="90:dd:5d:12:34:56")
        self.assertFalse(offline.known)
        self.assertFalse(offline.online)
        self.assertEqual(offline.status, Device.Status.OFFLINE)

    def test_watchyourlan_inventory_import_updates_existing_device_by_mac(self):
        response = self.client.post(
            "/api/v1/devices/import/watchyourlan/",
            [
                {
                    "Name": "Migrated laptop",
                    "DNS": "migrated-laptop.local",
                    "IP": "192.168.1.40",
                    "Mac": "aa:aa:aa:aa:aa:aa",
                    "Hw": "Example vendor",
                    "Date": "2026-08-29 11:00:00",
                    "Known": 1,
                    "Now": 1,
                }
            ],
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["updated"], 1)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Migrated laptop")
        self.assertEqual(self.device.ip, "192.168.1.40")
        self.assertEqual(self.device.hostname, "migrated-laptop.local")
        self.assertTrue(self.device.known)

    def test_watchyourlan_inventory_import_rejects_other_json_shapes(self):
        response = self.client.post(
            "/api/v1/devices/import/watchyourlan/",
            {"devices": []},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("WatchYourLAN", response.data["detail"])

        response = self.client.post(
            "/api/v1/devices/import/watchyourlan/",
            [
                {
                    "name": "LanGuard device",
                    "ip": "192.168.1.60",
                    "mac": "90:dd:5d:12:34:60",
                }
            ],
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("WatchYourLAN", response.data["detail"])

    def test_watchyourlan_inventory_import_requires_admin(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/devices/import/watchyourlan/",
            [],
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_netalertx_inventory_import_maps_devices_csv(self):
        csv_content = (
            '"devMac","devName","devType","devVendor","devComments",'
            '"devFirstConnection","devLastConnection","devLastIP",'
            '"devPresentLastScan","devIsNew","devLocation","devFQDN"\n'
            '"b0:be:76:12:34:56","Living Room TV","Television",'
            '"TP-Link Systems Inc.","Imported, verified",'
            '"2026-09-01 10:00:00+00:00","2026-09-05 07:30:00+00:00",'
            '"192.168.1.50","1","0","Living room","tv.local"\n'
            '"90:dd:5d:12:34:56","Guest phone","Smartphone","Apple, Inc.",'
            '"","2026-09-02 11:00:00+00:00","2026-09-04 18:00:00+00:00",'
            '"192.168.1.51","0","1","Guest room",""\n'
            '"Internet","Internet","Gateway","","",'
            '"2026-09-01 10:00:00+00:00","2026-09-05 07:30:00+00:00",'
            '"192.168.1.1","1","0","",""\n'
        )

        response = self.client.post(
            "/api/v1/devices/import/netalertx/",
            {"content": csv_content},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["created"], 2)
        self.assertEqual(response.data["data"]["skipped"], 1)
        television = Device.objects.get(mac="b0:be:76:12:34:56")
        self.assertEqual(television.name, "Living Room TV")
        self.assertEqual(television.hostname, "tv.local")
        self.assertEqual(television.hostname_source, Device.IdentitySource.IMPORTED)
        self.assertEqual(television.vendor, "TP-Link Systems Inc.")
        self.assertEqual(television.vendor_source, Device.IdentitySource.IMPORTED)
        self.assertEqual(television.comments, "Imported, verified")
        self.assertEqual(television.room, "Living room")
        self.assertEqual(television.role, "tv")
        self.assertTrue(television.known)
        self.assertTrue(television.online)
        self.assertEqual(television.status, Device.Status.ONLINE)
        phone = Device.objects.get(mac="90:dd:5d:12:34:56")
        self.assertEqual(phone.role, "phone")
        self.assertFalse(phone.known)
        self.assertFalse(phone.online)
        self.assertEqual(phone.status, Device.Status.OFFLINE)

    def test_netalertx_inventory_import_updates_existing_device_by_mac(self):
        csv_content = (
            "devMac,devName,devType,devVendor,devLastIP,devPresentLastScan,"
            "devIsNew,devLocation\n"
            "aa:aa:aa:aa:aa:aa,Migrated server,NAS,Example vendor,"
            "192.168.1.40,1,0,Office\n"
        )

        response = self.client.post(
            "/api/v1/devices/import/netalertx/",
            {"content": csv_content},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["updated"], 1)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Migrated server")
        self.assertEqual(self.device.ip, "192.168.1.40")
        self.assertEqual(self.device.role, "nas")
        self.assertEqual(self.device.room, "Office")
        self.assertTrue(self.device.known)

    def test_netalertx_inventory_import_rejects_other_csv_shapes(self):
        response = self.client.post(
            "/api/v1/devices/import/netalertx/",
            {"content": "name,ip,mac\nDevice,192.168.1.60,90:dd:5d:12:34:60\n"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("NetAlertX", response.data["detail"])

    def test_netalertx_inventory_import_requires_admin(self):
        regular_user = User.objects.create_user(
            username="netalertx-viewer",
            password="password",
        )
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/devices/import/netalertx/",
            {"content": "devMac,devLastIP\n"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_device_inventory_import_restores_comments_and_acknowledges_current_risk(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Remote workstation",
                        "ip": "192.168.1.20",
                        "mac": "aa:aa:aa:aa:aa:aa",
                        "vendor": "Example vendor",
                        "known": True,
                        "comments": "Remote Desktop is expected.",
                        "external_url": "http://192.168.1.20:8080",
                        "external_url_follow_device_ip": True,
                        "attention_acknowledged": True,
                        "open_ports": [3389],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.comments, "Remote Desktop is expected.")
        self.assertEqual(self.device.external_url, "http://192.168.1.20:8080")
        self.assertTrue(self.device.external_url_follow_device_ip)
        imported = self.client.get("/api/v1/device/", {"id": self.device.id}).data["data"]
        self.assertTrue(imported["attention_acknowledged"])
        self.assertFalse(imported["needs_attention"])

    def test_device_inventory_import_updates_existing_device_room(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Laptop",
                        "ip": "192.168.1.10",
                        "mac": "aa:aa:aa:aa:aa:aa",
                        "roomName": "Office",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.room, "Office")

    def test_device_inventory_import_preserves_existing_room_when_missing(self):
        self.device.room = "Living Room"
        self.device.save(update_fields=["room"])

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Laptop",
                        "ip": "192.168.1.10",
                        "mac": "aa:aa:aa:aa:aa:aa",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.room, "Living Room")

    def test_device_inventory_import_updates_existing_device_role(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Laptop",
                        "ip": "192.168.1.10",
                        "mac": "aa:aa:aa:aa:aa:aa",
                        "deviceRole": "meshRouter",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.role, "meshRouter")

    def test_device_inventory_import_preserves_existing_role_when_missing(self):
        self.device.role = "camera"
        self.device.save(update_fields=["role"])

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Laptop",
                        "ip": "192.168.1.10",
                        "mac": "aa:aa:aa:aa:aa:aa",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.role, "camera")

    def test_device_inventory_import_creates_new_device(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Camera",
                        "ip": "192.168.1.60",
                        "mac": "bb:bb:bb:bb:bb:bb",
                        "vendor": "Reolink",
                        "icon": "security-camera",
                        "known": True,
                        "open_ports": [554],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["created"], 1)
        imported = Device.objects.get(mac="bb:bb:bb:bb:bb:bb")
        self.assertEqual(imported.name, "Camera")
        self.assertEqual(imported.ports.get().port, 554)

    def test_device_inventory_import_removes_stale_ip_duplicate(self):
        stale = Device.objects.create(
            name="Old randomized device",
            ip="192.168.1.60",
            mac="b2:e9:86:9f:ef:ed",
            known=True,
            status=Device.Status.OFFLINE,
            online=False,
        )
        DevicePort.objects.create(device=stale, port=445, protocol="tcp", open=True)

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Camera",
                        "ip": "192.168.1.60",
                        "mac": "bb:bb:bb:bb:bb:bb",
                        "vendor": "Reolink",
                        "icon": "security-camera",
                        "known": True,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["removed_duplicates"], 1)
        self.assertFalse(Device.objects.filter(mac="b2:e9:86:9f:ef:ed").exists())
        self.assertFalse(DevicePort.objects.filter(device=stale).exists())
        self.assertTrue(Device.objects.filter(mac="bb:bb:bb:bb:bb:bb").exists())

    def test_device_inventory_import_keeps_active_known_ip_duplicate(self):
        active = Device.objects.create(
            name="Active server",
            ip="192.168.1.60",
            mac="48:0f:cf:5c:f5:2e",
            known=True,
            status=Device.Status.ONLINE,
            online=True,
        )

        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Camera",
                        "ip": "192.168.1.60",
                        "mac": "bb:bb:bb:bb:bb:bb",
                        "known": True,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["removed_duplicates"], 0)
        self.assertTrue(Device.objects.filter(pk=active.pk).exists())
        self.assertTrue(Device.objects.filter(mac="bb:bb:bb:bb:bb:bb").exists())
        self.assertEqual(
            DeviceIPAddressAssignment.objects.filter(
                ip="192.168.1.60",
                valid_until__isnull=True,
            ).count(),
            2,
        )

    def test_device_inventory_import_accepts_macos_export_shape(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "exported_at": 790000000,
                "devices": [
                    {
                        "name": "Guest Sensor",
                        "ip": "192.168.1.70",
                        "mac": "AA-BB-CC-DD-EE-FF",
                        "vendor": "Example",
                        "hostname": "sensor.local",
                        "icon": "thermometer.medium",
                        "secondary_icon": "light.strip.2",
                        "role": "sensor",
                        "room": "Kitchen",
                        "known": True,
                        "is_visitor": True,
                        "is_gateway": False,
                        "status": "online",
                        "open_ports": [80, "443", 80],
                        "first_seen": 790000000,
                        "last_seen": 790000060,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        imported = Device.objects.get(mac="aa:bb:cc:dd:ee:ff")
        self.assertEqual(imported.icon, "thermostat")
        self.assertEqual(imported.secondary_icon, "led-strip")
        self.assertEqual(imported.role, "sensor")
        self.assertEqual(imported.room, "Kitchen")
        self.assertTrue(imported.known)
        self.assertTrue(imported.is_visitor)
        self.assertEqual(
            list(imported.ports.filter(open=True).values_list("port", flat=True)),
            [80, 443],
        )

    def test_device_inventory_import_preserves_macos_export_fields(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "exported_at": 790000000,
                "devices": [
                    {
                        "name": "Office Router",
                        "ip": "192.168.1.1",
                        "mac": "AA-BB-CC-DD-EE-10",
                        "vendor": "TP-Link Technologies Co., Ltd.",
                        "hostname": "office-router.local",
                        "icon": "wifi.router",
                        "secondary_icon": "server.rack",
                        "role": "meshRouter",
                        "room": "Office",
                        "known": True,
                        "is_gateway": True,
                        "status": "online",
                        "risk": "medium",
                        "open_ports": [22, 80, "443", 80],
                        "first_seen": 790000000,
                        "last_seen": 790000060,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        imported = Device.objects.get(mac="aa:bb:cc:dd:ee:10")
        self.assertEqual(imported.name, "Office Router")
        self.assertEqual(imported.ip, "192.168.1.1")
        self.assertEqual(imported.vendor, "TP-Link Technologies Co., Ltd.")
        self.assertEqual(imported.hostname, "office-router.local")
        self.assertEqual(imported.icon, "router")
        self.assertEqual(imported.secondary_icon, "server")
        self.assertEqual(imported.role, "meshRouter")
        self.assertEqual(imported.room, "Office")
        self.assertTrue(imported.known)
        self.assertTrue(imported.is_gateway)
        self.assertTrue(imported.online)
        self.assertEqual(imported.status, Device.Status.ONLINE)
        self.assertEqual(imported.firstseen, parse_inventory_datetime(790000000, timezone.now()))
        self.assertEqual(imported.lastseen, parse_inventory_datetime(790000060, timezone.now()))
        self.assertEqual(
            list(imported.ports.filter(open=True).values_list("port", flat=True)),
            [22, 80, 443],
        )

    def test_device_inventory_import_maps_macos_icon_catalog(self):
        response = self.client.post(
            "/api/v1/devices/import/",
            {
                "format": "languard-device-inventory",
                "version": 1,
                "devices": [
                    {
                        "name": "Speaker",
                        "ip": "192.168.1.71",
                        "mac": "aa:bb:cc:dd:ee:01",
                        "icon": "hifispeaker",
                        "known": True,
                    },
                    {
                        "name": "Switch",
                        "ip": "192.168.1.72",
                        "mac": "aa:bb:cc:dd:ee:02",
                        "icon": "lightswitch.on",
                        "secondary_icon": "powerplug",
                        "known": True,
                    },
                    {
                        "name": "Controller",
                        "ip": "192.168.1.73",
                        "mac": "aa:bb:cc:dd:ee:03",
                        "icon": "switch.2",
                        "known": True,
                    },
                    {
                        "name": "Unknown Symbol",
                        "ip": "192.168.1.74",
                        "mac": "aa:bb:cc:dd:ee:04",
                        "icon": "not.a.real.symbol",
                        "known": True,
                    },
                    {
                        "name": "Climate Sensor",
                        "ip": "192.168.1.75",
                        "mac": "aa:bb:cc:dd:ee:05",
                        "icon": "humidity",
                        "known": True,
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Device.objects.get(mac="aa:bb:cc:dd:ee:01").icon, "speaker")
        switch = Device.objects.get(mac="aa:bb:cc:dd:ee:02")
        self.assertEqual(switch.icon, "light")
        self.assertEqual(switch.secondary_icon, "power-strip")
        self.assertEqual(Device.objects.get(mac="aa:bb:cc:dd:ee:03").icon, "smart-hub")
        self.assertEqual(Device.objects.get(mac="aa:bb:cc:dd:ee:04").icon, "unknown")
        self.assertEqual(
            Device.objects.get(mac="aa:bb:cc:dd:ee:05").icon,
            "temperature-humidity-sensor",
        )
