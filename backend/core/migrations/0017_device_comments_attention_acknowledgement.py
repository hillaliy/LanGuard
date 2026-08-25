from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0016_activity_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="comments",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="device",
            name="attention_acknowledged_signature",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
