from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_appsettings_notification_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="is_gateway",
            field=models.BooleanField(default=False),
        ),
    ]
