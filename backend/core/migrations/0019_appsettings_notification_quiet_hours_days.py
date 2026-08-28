from django.db import migrations, models

import core.models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_device_external_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="notification_quiet_hours_days",
            field=models.JSONField(
                blank=True,
                default=core.models.default_quiet_hours_days,
            ),
        ),
    ]
