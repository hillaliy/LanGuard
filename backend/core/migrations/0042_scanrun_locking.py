import django.db.models
import django.utils.timezone
from django.db import migrations, models


def finish_interrupted_scans(apps, schema_editor):
    ScanRun = apps.get_model("core", "ScanRun")
    now = django.utils.timezone.now()
    ScanRun.objects.filter(status="running").update(
        status="failed",
        finished_at=now,
        heartbeat_at=now,
        error="Scan was interrupted while scan locking was enabled.",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0041_appsettings_telegram_api_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="scanrun",
            name="heartbeat_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="scanrun",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("scheduled", "Scheduled"),
                    ("command", "Command"),
                ],
                default="command",
                max_length=16,
            ),
        ),
        migrations.RunPython(finish_interrupted_scans, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="scanrun",
            constraint=models.UniqueConstraint(
                condition=django.db.models.Q(("status", "running")),
                fields=("status",),
                name="one_active_network_scan",
            ),
        ),
    ]
