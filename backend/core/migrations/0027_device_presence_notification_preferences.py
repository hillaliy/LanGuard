from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_alter_device_status_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="offline_notification_preference",
            field=models.CharField(
                choices=[
                    ("inherit", "Use global setting"),
                    ("always", "Always notify"),
                    ("never", "Never notify"),
                ],
                default="inherit",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="device",
            name="online_notification_preference",
            field=models.CharField(
                choices=[
                    ("inherit", "Use global setting"),
                    ("always", "Always notify"),
                    ("never", "Never notify"),
                ],
                default="inherit",
                max_length=16,
            ),
        ),
    ]
