from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0044_alter_networkevent_event_type_dockerhost_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="scanrun",
            name="failure_code",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="scanrun",
            name="failure_fingerprint",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="scanrun",
            name="failure_stage",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="scanrun",
            name="failure_type",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
