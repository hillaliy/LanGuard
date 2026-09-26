from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_deviceipaddressassignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="telegram_api_url",
            field=models.URLField(
                default="https://api.telegram.org",
                max_length=2048,
            ),
        ),
    ]
