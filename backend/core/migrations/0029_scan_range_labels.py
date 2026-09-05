import core.models
from django.db import migrations, models


def populate_scan_range_labels(apps, schema_editor):
    AppSettings = apps.get_model("core", "AppSettings")
    ScanRun = apps.get_model("core", "ScanRun")

    current_labels = {}
    config = AppSettings.objects.first()
    if config:
        ranges = config.scan_ranges or [config.ip_range]
        current_labels = {
            network_range: (
                "Primary network" if index == 0 else f"Network {index + 1}"
            )
            for index, network_range in enumerate(ranges)
        }
        config.scan_range_labels = current_labels
        config.save(update_fields=["scan_range_labels"])

    for run in ScanRun.objects.all().iterator():
        ranges = run.scan_ranges or [run.ip_range]
        run.scan_range_labels = {
            network_range: current_labels[network_range]
            for network_range in ranges
            if network_range in current_labels
        }
        run.save(update_fields=["scan_range_labels"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_multi_network_scan_ranges"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="scan_range_labels",
            field=models.JSONField(
                blank=True,
                default=core.models.default_scan_range_labels,
            ),
        ),
        migrations.AddField(
            model_name="scanrun",
            name="scan_range_labels",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(populate_scan_range_labels, migrations.RunPython.noop),
    ]
