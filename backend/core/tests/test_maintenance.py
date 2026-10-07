from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import (
    AppSettings,
    Device,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)


class MaintenanceApiTests(TestCase):
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

    def test_diagnostics_export_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.get("/api/v1/diagnostics/export/")

        self.assertEqual(response.status_code, 403)

    def test_diagnostics_export_omits_secrets_and_device_identifiers(self):
        config = AppSettings.load()
        config.discord_webhook = "https://discord.example/super-secret-webhook"
        config.telegram_token = "super-secret-bot-token"
        config.telegram_user_id = "987654321"
        config.webhook_enabled = True
        config.webhook_url = "https://automation.example/private-webhook"
        config.webhook_secret = "super-secret-signing-key"
        config.adguard_enabled = True
        config.adguard_url = "http://10.20.30.40:3000"
        config.adguard_username = "private-admin"
        config.adguard_password = "super-secret-password"
        config.adguard_last_error = "Connection failed at http://10.20.30.40/private"
        config.speedtest_tracker_enabled = True
        config.speedtest_tracker_url = "http://10.20.30.50:8080"
        config.speedtest_tracker_api_token = "super-secret-speedtest-token"
        config.snmp_enabled = True
        config.snmp_community = "super-secret-snmp-community"
        config.save()
        self.scan_run.error = "Failed on 192.168.1.20 with aa:aa:aa:aa:aa:aa"
        self.scan_run.status = ScanRun.Status.FAILED
        self.scan_run.failure_code = "database_locked"
        self.scan_run.failure_type = "OperationalError"
        self.scan_run.failure_stage = "device_sync"
        self.scan_run.failure_fingerprint = "0123456789abcdef"
        self.scan_run.save(
            update_fields=[
                "error",
                "status",
                "failure_code",
                "failure_type",
                "failure_stage",
                "failure_fingerprint",
            ]
        )
        self.delivery.error = (
            "POST https://api.telegram.org/botsuper-secret-bot-token/sendMessage failed"
        )
        self.delivery.save(update_fields=["error"])

        with TemporaryDirectory() as temporary_directory:
            missing_log = Path(temporary_directory) / "missing.log"
            with override_settings(
                DIAGNOSTIC_LOG_FILES={"backend": missing_log},
                LOG_BACKUP_COUNT=0,
            ):
                response = self.client.get("/api/v1/diagnostics/export/")

        self.assertEqual(response.status_code, 200)
        serialized = str(response.data)
        for private_value in (
            "super-secret-webhook",
            "super-secret-bot-token",
            "super-secret-password",
            "super-secret-signing-key",
            "private-webhook",
            "private-admin",
            "10.20.30.40",
            "10.20.30.50",
            "super-secret-speedtest-token",
            "super-secret-snmp-community",
            "192.168.1.20",
            "aa:aa:aa:aa:aa:aa",
            "Laptop",
        ):
            self.assertNotIn(private_value, serialized)
        self.assertEqual(
            response.data["data"]["report"]["report"]["format"],
            "languard-diagnostics",
        )
        diagnostics = response.data["data"]["report"]
        self.assertEqual(diagnostics["report"]["format_version"], 3)
        latest_scan = diagnostics["latest_scans"][0]
        self.assertEqual(latest_scan["failure_code"], "database_locked")
        self.assertEqual(latest_scan["failure_type"], "OperationalError")
        self.assertEqual(latest_scan["failure_stage"], "device_sync")
        self.assertEqual(latest_scan["failure_fingerprint"], "0123456789abcdef")
        recent_failure = diagnostics["recent_scan_failures"][0]
        self.assertEqual(recent_failure["failure_code"], "database_locked")
        self.assertEqual(
            diagnostics["scan_failure_summary"]["by_stage"],
            [{"value": "device_sync", "count": 1}],
        )
        self.assertFalse(diagnostics["logs"]["sources"][0]["available"])
        configuration = response.data["data"]["report"]["configuration"]
        self.assertTrue(configuration["speedtest_tracker_enabled"])
        self.assertTrue(configuration["speedtest_tracker_configured"])
        self.assertTrue(configuration["snmp_enabled"])
        self.assertTrue(configuration["snmp_configured"])
        self.assertIn("notification", response.data)

    def test_diagnostics_export_includes_sanitized_failure_logs(self):
        with TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "scheduler.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-10-06 08:00:00 : INFO - Starting scan for 192.168.1.0/24",
                        "2026-10-06 08:00:01 : ERROR - Admin failed Laptop scan at "
                        "https://private.example/run?token=secret on 192.168.1.20",
                        "Traceback (most recent call last):",
                        '  File "/app/core/scanning/orchestration.py", line 144, in scan',
                        '    raise TimeoutError("aa:aa:aa:aa:aa:aa")',
                        "requests.exceptions.Timeout: token=secret 192.168.1.20",
                    ]
                ),
                encoding="utf-8",
            )
            with override_settings(
                DIAGNOSTIC_LOG_FILES={"scheduler": log_path},
                LOG_BACKUP_COUNT=0,
            ):
                response = self.client.get("/api/v1/diagnostics/export/")

        self.assertEqual(response.status_code, 200)
        logs = response.data["data"]["report"]["logs"]
        self.assertEqual(len(logs["events"]), 1)
        event = logs["events"][0]
        self.assertEqual(event["component"], "scheduler")
        self.assertEqual(event["level"], "ERROR")
        self.assertIn("[url]", event["message"])
        self.assertIn("[ip]", event["message"])
        self.assertEqual(event["exception_type"], "requests.exceptions.Timeout")
        self.assertEqual(
            event["traceback"],
            [
                {
                    "file": "core/scanning/orchestration.py",
                    "line": 144,
                    "function": "scan",
                }
            ],
        )
        serialized = str(logs)
        for private_value in (
            "private.example",
            "token=secret",
            "192.168.1.20",
            "aa:aa:aa:aa:aa:aa",
            "/app/",
            "Laptop",
            "Admin",
        ):
            self.assertNotIn(private_value, serialized)

    def test_old_raw_errors_are_sanitized_in_api_responses(self):
        self.scan_run.error = "Internal path /private/app and 192.168.1.20"
        self.scan_run.save(update_fields=["error"])
        self.delivery.error = "https://discord.example/private-webhook"
        self.delivery.save(update_fields=["error"])

        scans = self.client.get("/api/v1/scan/runs/").data
        deliveries = self.client.get("/api/v1/notifications/").data

        self.assertNotIn("/private/app", str(scans))
        self.assertNotIn("192.168.1.20", str(scans))
        self.assertNotIn("private-webhook", str(deliveries))

    def test_maintenance_cleanup_requires_admin_user(self):
        regular_user = User.objects.create_user(username="viewer", password="password")
        regular_client = APIClient()
        regular_client.force_authenticate(regular_user)

        response = regular_client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": 30},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_maintenance_cleanup_deletes_old_events_only(self):
        old_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.SUCCESS,
            started_at=timezone.now() - timedelta(days=400),
            finished_at=timezone.now() - timedelta(days=400),
        )
        old_event = NetworkEvent.objects.create(
            scan_run=old_scan,
            device=self.device,
            event_type=NetworkEvent.EventType.DEVICE_OFFLINE,
            message="Laptop went offline",
            created_at=timezone.now() - timedelta(days=400),
        )
        old_delivery = NotificationDelivery.objects.create(
            event=old_event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.SENT,
            created_at=timezone.now() - timedelta(days=400),
        )
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
            started_at=timezone.now() - timedelta(days=400),
        )

        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["target"], "events")
        self.assertEqual(response.data["data"]["deleted"]["events"], 1)
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 0)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 0)
        self.assertFalse(NetworkEvent.objects.filter(id=old_event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=old_delivery.id).exists())
        old_delivery.refresh_from_db()
        self.assertIsNone(old_delivery.event_id)
        self.assertTrue(ScanRun.objects.filter(id=old_scan.id).exists())
        self.assertTrue(ScanRun.objects.filter(id=running_scan.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())
        self.assertTrue(ScanRun.objects.filter(id=self.scan_run.id).exists())

    def test_maintenance_cleanup_clean_all_deletes_current_events(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "clean_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["clean_all"])
        self.assertEqual(response.data["data"]["deleted"]["events"], 1)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 0)
        self.assertFalse(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())
        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.event_id)

    def test_maintenance_cleanup_clean_all_deletes_current_scan_runs(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "scan_runs", "clean_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["clean_all"])
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 1)
        self.assertFalse(ScanRun.objects.filter(id=self.scan_run.id).exists())

    def test_maintenance_cleanup_clean_all_deletes_current_notifications(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "notifications", "clean_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["clean_all"])
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 1)
        self.assertFalse(NotificationDelivery.objects.filter(id=self.delivery.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())

    def test_maintenance_cleanup_rejects_zero_day_retention(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": 0},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("older_than_days", response.data)

    def test_maintenance_cleanup_deletes_old_scan_runs_only(self):
        old_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.SUCCESS,
            started_at=timezone.now() - timedelta(days=400),
            finished_at=timezone.now() - timedelta(days=400),
        )
        running_scan = ScanRun.objects.create(
            ip_range="192.168.1.0/24",
            status=ScanRun.Status.RUNNING,
            started_at=timezone.now() - timedelta(days=400),
        )

        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "scan_runs", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["target"], "scan_runs")
        self.assertEqual(response.data["data"]["deleted"]["events"], 0)
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 1)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 0)
        self.assertFalse(ScanRun.objects.filter(id=old_scan.id).exists())
        self.assertTrue(ScanRun.objects.filter(id=running_scan.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())

    def test_maintenance_cleanup_deletes_old_notifications_only(self):
        old_delivery = NotificationDelivery.objects.create(
            event=self.event,
            channel=NotificationDelivery.Channel.DISCORD,
            status=NotificationDelivery.Status.SENT,
            created_at=timezone.now() - timedelta(days=400),
        )

        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "notifications", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["target"], "notifications")
        self.assertEqual(response.data["data"]["deleted"]["events"], 0)
        self.assertEqual(response.data["data"]["deleted"]["scan_runs"], 0)
        self.assertEqual(response.data["data"]["deleted"]["notifications"], 1)
        self.assertFalse(NotificationDelivery.objects.filter(id=old_delivery.id).exists())
        self.assertTrue(NetworkEvent.objects.filter(id=self.event.id).exists())
        self.assertTrue(NotificationDelivery.objects.filter(id=self.delivery.id).exists())

    def test_maintenance_cleanup_rejects_invalid_retention(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "events", "older_than_days": -1},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("older_than_days", response.data)

    def test_maintenance_cleanup_rejects_invalid_target(self):
        response = self.client.post(
            "/api/v1/maintenance/cleanup/",
            {"target": "devices", "older_than_days": 365},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("target", response.data)
