from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .detailed_port_scans import (
    claim_next_detailed_port_scan,
    parse_port_specification,
    process_next_detailed_port_scan,
    run_detailed_port_scan,
)
from .models import DetailedPortScan, Device, DevicePort, UserAccess


class DetailedPortSpecificationTests(SimpleTestCase):
    @override_settings(DETAILED_PORT_SCAN_MAX_PORTS=10)
    def test_parses_lists_ranges_and_duplicates(self):
        self.assertEqual(
            parse_port_specification("22, 80-82, 80, 443"),
            [22, 80, 81, 82, 443],
        )

    @override_settings(DETAILED_PORT_SCAN_MAX_PORTS=3)
    def test_rejects_too_many_ports(self):
        with self.assertRaisesRegex(ValueError, "at most 3"):
            parse_port_specification("1-4")

    def test_rejects_invalid_or_reversed_ranges(self):
        invalid_values = ("", "0", "65536", "80-22", "22-23-24", "abc")
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_port_specification(value)


@override_settings(
    NOTIFICATIONS_ENABLED=False,
    DETAILED_PORT_SCAN_MAX_PORTS=1024,
    DETAILED_PORT_SCAN_MAX_QUEUED=20,
    DETAILED_PORT_SCAN_TIMEOUT=0.01,
    DETAILED_PORT_SCAN_MAX_SECONDS=300,
)
class DetailedPortScanApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="scanner", password="password")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(
            name="Server",
            ip="192.168.1.40",
            mac="aa:bb:cc:dd:ee:01",
        )

    def test_starts_and_reads_detailed_scan(self):
        response = self.client.post(
            "/api/v1/device/port-scan/",
            {"device": self.device.id, "ports": "22, 80-82"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["data"]["status"], "queued")
        job = DetailedPortScan.objects.get(id=response.data["data"]["id"])
        self.assertEqual(job.ports, [22, 80, 81, 82])
        read_response = self.client.get(
            "/api/v1/device/port-scan/",
            {"device": self.device.id},
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.data["data"]["id"], response.data["data"]["id"])

    def test_rejects_second_active_scan_for_device(self):
        DetailedPortScan.objects.create(
            device=self.device,
            requested_by=self.user,
            ports=[22],
            total_ports=1,
        )

        response = self.client.post(
            "/api/v1/device/port-scan/",
            {"device": self.device.id, "ports": "80"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_user_needs_edit_or_scan_permission(self):
        UserAccess.objects.create(
            user=self.user,
            can_edit_devices=False,
            can_run_scans=False,
        )

        response = self.client.post(
            "/api/v1/device/port-scan/",
            {"device": self.device.id, "ports": "22"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_device_editor_can_start_scan_without_scan_permission(self):
        UserAccess.objects.create(
            user=self.user,
            can_edit_devices=True,
            can_run_scans=False,
        )

        response = self.client.post(
            "/api/v1/device/port-scan/",
            {"device": self.device.id, "ports": "443"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)

    def test_cancels_queued_scan_immediately(self):
        job = DetailedPortScan.objects.create(
            device=self.device,
            requested_by=self.user,
            ports=[22],
            total_ports=1,
        )

        response = self.client.post(
            "/api/v1/device/port-scan/cancel/",
            {"id": job.id},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        job.refresh_from_db()
        self.assertEqual(job.status, DetailedPortScan.Status.CANCELLED)
        self.assertTrue(job.cancel_requested)
        self.assertIsNotNone(job.finished_at)

    @patch("core.detailed_port_scans.scan_open_ports")
    def test_worker_scans_and_only_closes_ports_in_requested_scope(self, scan_ports):
        DevicePort.objects.create(device=self.device, port=80, open=True)
        requested_closed_port = DevicePort.objects.create(
            device=self.device,
            port=81,
            open=True,
        )
        job = DetailedPortScan.objects.create(
            device=self.device,
            requested_by=self.user,
            ports=[22, 81],
            total_ports=2,
        )
        scan_ports.side_effect = lambda ip, ports, timeout: (
            [{"port": 22, "protocol": "tcp", "service": "ssh"}]
            if ports == [22]
            else []
        )

        result = process_next_detailed_port_scan()

        result.refresh_from_db()
        requested_closed_port.refresh_from_db()
        self.assertEqual(result.status, DetailedPortScan.Status.SUCCESS)
        self.assertEqual(result.scanned_ports, 2)
        self.assertEqual(result.open_ports[0]["port"], 22)
        self.assertFalse(requested_closed_port.open)
        self.assertTrue(DevicePort.objects.get(device=self.device, port=80).open)
        self.assertTrue(DevicePort.objects.get(device=self.device, port=22).open)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_port_scan)

    @override_settings(DETAILED_PORT_SCAN_MAX_SECONDS=0)
    def test_worker_records_timeout(self):
        DetailedPortScan.objects.create(
            device=self.device,
            requested_by=self.user,
            ports=[22],
            total_ports=1,
        )

        result = process_next_detailed_port_scan()

        result.refresh_from_db()
        self.assertEqual(result.status, DetailedPortScan.Status.FAILED)
        self.assertIn("second limit", result.error)

    def test_running_scan_honors_cancellation_request(self):
        job = DetailedPortScan.objects.create(
            device=self.device,
            requested_by=self.user,
            ports=[22],
            total_ports=1,
        )
        running_job = claim_next_detailed_port_scan()
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested"])

        result = run_detailed_port_scan(running_job)

        result.refresh_from_db()
        self.assertEqual(result.status, DetailedPortScan.Status.CANCELLED)
