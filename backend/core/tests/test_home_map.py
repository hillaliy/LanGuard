
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import (
    AppSettings,
    Device,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)

class HomeMapApiTests(TestCase):
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

    def test_home_map_layout_endpoint_requires_authentication(self):
        client = APIClient()

        response = client.get("/api/v1/home-map-layout/")

        self.assertEqual(response.status_code, 401)

    def test_home_map_layout_endpoint_saves_layout_for_authenticated_user(self):
        layout = {
            "order": ["Floor", "Bedroom", "Basement", "Outside"],
            "parents": {"Bedroom": "Floor"},
            "icons": {
                "Floor": "home",
                "Bedroom": "bedroom",
                "Basement": "basement",
                "Outside": "outside",
            },
            "placements": {"Floor": 0, "Bedroom": 4},
            "sizes": {"Floor": 8, "Bedroom": 3},
        }

        response = self.client.put(
            "/api/v1/home-map-layout/",
            {"layout": layout},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["layout"], layout)
        self.assertEqual(AppSettings.load().home_map_layout, layout)

        get_response = self.client.get("/api/v1/home-map-layout/")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.data["data"]["layout"], layout)

    def test_home_map_layout_endpoint_rejects_invalid_layout(self):
        response = self.client.put(
            "/api/v1/home-map-layout/",
            {"layout": {"order": "Floor", "parents": {}}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_home_map_layout_endpoint_accepts_legacy_layout_without_icons(self):
        layout = {
            "order": ["Office"],
            "parents": {},
        }

        response = self.client.put(
            "/api/v1/home-map-layout/",
            {"layout": layout},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["layout"], layout)

    def test_home_map_layout_endpoint_rejects_unknown_room_icon(self):
        response = self.client.put(
            "/api/v1/home-map-layout/",
            {
                "layout": {
                    "order": ["Office"],
                    "parents": {},
                    "icons": {"Office": "custom-svg"},
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_home_map_layout_endpoint_rejects_malformed_icon_metadata(self):
        response = self.client.put(
            "/api/v1/home-map-layout/",
            {
                "layout": {
                    "order": ["Office"],
                    "parents": {},
                    "icons": ["office"],
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_home_map_layout_endpoint_rejects_invalid_room_placement(self):
        response = self.client.put(
            "/api/v1/home-map-layout/",
            {
                "layout": {
                    "order": ["Office"],
                    "parents": {},
                    "placements": {"Office": -1},
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_home_map_layout_endpoint_rejects_invalid_room_size(self):
        response = self.client.put(
            "/api/v1/home-map-layout/",
            {
                "layout": {
                    "order": ["Office"],
                    "parents": {},
                    "sizes": {"Office": 1},
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
