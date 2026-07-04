from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_appsettings_channel_toggles"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="status",
            field=models.CharField(
                choices=[
                    ("online", "Online"),
                    ("recently_seen", "Recently seen"),
                    ("sleeping", "Sleeping"),
                    ("offline", "Offline"),
                ],
                default="online",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="device",
            name="status_source",
            field=models.CharField(
                choices=[
                    ("arp", "ARP"),
                    ("port", "Port"),
                    ("icmp", "ICMP"),
                    ("recent", "Recent"),
                    ("none", "None"),
                ],
                default="arp",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="device",
            name="status_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="device",
            name="last_status_check",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
