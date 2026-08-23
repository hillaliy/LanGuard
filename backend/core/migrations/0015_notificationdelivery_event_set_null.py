from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_appsettings_activity_cleanup_retention_days"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationdelivery",
            name="event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications",
                to="core.networkevent",
            ),
        ),
    ]
