from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_device_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="home_map_layout",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
