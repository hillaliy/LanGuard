from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0038_appsettings_ntfy_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="external_url_follow_device_ip",
            field=models.BooleanField(default=False),
        ),
    ]
