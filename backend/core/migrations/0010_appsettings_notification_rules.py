from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_appsettings_version_check_interval"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="notify_new_devices",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notify_device_online",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notify_device_offline",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notify_port_changes",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notification_quiet_hours_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notification_quiet_hours_start",
            field=models.CharField(default="22:00", max_length=5),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notification_quiet_hours_end",
            field=models.CharField(default="07:00", max_length=5),
        ),
    ]
