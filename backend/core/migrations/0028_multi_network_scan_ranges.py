import core.models
from django.db import migrations, models


def copy_primary_ranges(apps, schema_editor):
    AppSettings = apps.get_model("core", "AppSettings")
    ScanRun = apps.get_model("core", "ScanRun")

    for config in AppSettings.objects.all().iterator():
        config.scan_ranges = [config.ip_range]
        config.save(update_fields=["scan_ranges"])

    for run in ScanRun.objects.all().iterator():
        run.scan_ranges = [run.ip_range]
        run.save(update_fields=["scan_ranges"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0027_device_presence_notification_preferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="scan_ranges",
            field=models.JSONField(blank=True, default=core.models.default_scan_ranges),
        ),
        migrations.AddField(
            model_name="scanrun",
            name="scan_ranges",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_primary_ranges, migrations.RunPython.noop),
    ]
