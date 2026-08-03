from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_device_is_gateway"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="hostname",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="device",
            name="room",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="device",
            name="role",
            field=models.CharField(blank=True, default="device", max_length=32),
        ),
        migrations.AddField(
            model_name="device",
            name="secondary_icon",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
