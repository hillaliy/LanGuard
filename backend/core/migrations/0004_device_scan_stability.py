from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_scan_events_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="last_port_scan",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="device",
            name="missed_scans",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
