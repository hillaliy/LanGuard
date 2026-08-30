from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_adguard_home_integration"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdGuardUnmatchedClient",
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
                ("client", models.CharField(max_length=255, unique=True)),
                ("query_count", models.PositiveBigIntegerField(default=0)),
                ("blocked_count", models.PositiveBigIntegerField(default=0)),
                ("first_seen", models.DateTimeField()),
                ("last_seen", models.DateTimeField()),
                ("last_domain", models.CharField(blank=True, default="", max_length=253)),
                ("last_status", models.CharField(blank=True, default="", max_length=32)),
                ("last_reason", models.CharField(blank=True, default="", max_length=64)),
            ],
            options={
                "ordering": ["-last_seen", "client"],
                "indexes": [
                    models.Index(fields=["-last_seen"], name="core_ag_unmatched_seen_idx"),
                    models.Index(fields=["-query_count"], name="core_ag_unmatched_query_idx"),
                ],
            },
        ),
    ]
