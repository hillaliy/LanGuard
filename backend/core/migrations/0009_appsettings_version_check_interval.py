from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_device_status_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="version_check_interval",
            field=models.PositiveIntegerField(default=21600),
        ),
    ]
