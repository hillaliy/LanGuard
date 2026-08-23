from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_notificationdelivery_event_set_null"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="scanrun",
            index=models.Index(
                fields=["-started_at"],
                name="core_scanrun_started_desc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="scanrun",
            index=models.Index(
                fields=["status", "-started_at"],
                name="core_scanrun_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="networkevent",
            index=models.Index(
                fields=["-created_at"],
                name="core_event_created_desc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="networkevent",
            index=models.Index(
                fields=["event_type", "-created_at"],
                name="core_event_type_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="networkevent",
            index=models.Index(
                fields=["notified", "-created_at"],
                name="core_event_notified_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["-created_at"],
                name="core_notify_created_desc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["channel", "-created_at"],
                name="core_notify_channel_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["status", "-created_at"],
                name="core_notify_status_created_idx",
            ),
        ),
    ]
