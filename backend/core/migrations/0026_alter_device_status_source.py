from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_appsettings_speedtest_tracker_api_token_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="device",
            name="status_source",
            field=models.CharField(
                choices=[
                    ("arp", "ARP"),
                    ("local", "Local scanner"),
                    ("port", "Port"),
                    ("icmp", "ICMP"),
                    ("recent", "Recent"),
                    ("none", "None"),
                ],
                default="arp",
                max_length=32,
            ),
        ),
    ]
