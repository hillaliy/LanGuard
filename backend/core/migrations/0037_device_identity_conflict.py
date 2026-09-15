from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0036_detailedportscan"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="identity_conflict_detected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="device",
            name="identity_conflict_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
