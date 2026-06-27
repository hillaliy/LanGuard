from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="device",
            options={"ordering": ["-online", "name", "ip"]},
        ),
        migrations.AddField(
            model_name="device",
            name="firstseen",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="device",
            name="icon",
            field=models.CharField(default="plus", max_length=255),
        ),
        migrations.AlterField(
            model_name="device",
            name="ip",
            field=models.GenericIPAddressField(),
        ),
        migrations.AlterField(
            model_name="device",
            name="mac",
            field=models.CharField(max_length=17, unique=True),
        ),
        migrations.AlterField(
            model_name="device",
            name="name",
            field=models.CharField(default="Device", max_length=100),
        ),
        migrations.AlterField(
            model_name="device",
            name="vendor",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.CreateModel(
            name="DevicePort",
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
                ("port", models.PositiveIntegerField()),
                ("protocol", models.CharField(default="tcp", max_length=8)),
                ("service", models.CharField(blank=True, default="", max_length=64)),
                ("open", models.BooleanField(default=True)),
                ("firstseen", models.DateTimeField(default=django.utils.timezone.now)),
                ("lastseen", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ports",
                        to="core.device",
                    ),
                ),
            ],
            options={
                "ordering": ["port"],
            },
        ),
        migrations.AddConstraint(
            model_name="deviceport",
            constraint=models.UniqueConstraint(
                fields=("device", "port", "protocol"),
                name="unique_device_port_protocol",
            ),
        ),
    ]
