from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0037_device_identity_conflict"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="ntfy_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="ntfy_priority",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Min"),
                    (2, "Low"),
                    (3, "Default"),
                    (4, "High"),
                    (5, "Max"),
                ],
                default=3,
            ),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="ntfy_server_url",
            field=models.URLField(blank=True, default="", max_length=2048),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="ntfy_topic",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="notificationdelivery",
            name="channel",
            field=models.CharField(
                choices=[
                    ("discord", "Discord"),
                    ("telegram", "Telegram"),
                    ("ntfy", "ntfy"),
                    ("webhook", "Webhook"),
                ],
                max_length=32,
            ),
        ),
    ]
