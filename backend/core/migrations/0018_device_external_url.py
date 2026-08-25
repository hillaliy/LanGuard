from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_device_comments_attention_acknowledgement"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="external_url",
            field=models.URLField(blank=True, default="", max_length=2048),
        ),
    ]
