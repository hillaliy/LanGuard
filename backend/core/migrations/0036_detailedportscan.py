import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0035_appsettings_notify_speedtest_changes_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DetailedPortScan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ports", models.JSONField(default=list)),
                ("open_ports", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("success", "Success"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="queued", max_length=16)),
                ("total_ports", models.PositiveIntegerField(default=0)),
                ("scanned_ports", models.PositiveIntegerField(default=0)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.CharField(blank=True, default="", max_length=255)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="detailed_port_scans", to="core.device")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="detailed_port_scans", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="core_detail_scan_queue_idx"),
                    models.Index(fields=["device", "-created_at"], name="core_detail_scan_device_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("status__in", ["queued", "running"])), fields=("device",), name="one_active_detailed_scan_per_device"),
                ],
            },
        ),
    ]
