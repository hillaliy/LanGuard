from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_devicerelatedlink"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchedulerRuntimeState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "singleton_key",
                    models.PositiveSmallIntegerField(
                        default=1,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("next_scan_at", models.DateTimeField(blank=True, null=True)),
                ("stopped_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Scheduler runtime state",
                "verbose_name_plural": "Scheduler runtime state",
            },
        ),
    ]
