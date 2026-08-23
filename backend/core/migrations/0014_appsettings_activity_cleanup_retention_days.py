from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_appsettings_home_map_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="activity_cleanup_retention_days",
            field=models.PositiveIntegerField(default=90),
        ),
    ]
