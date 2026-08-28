from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_appsettings_notification_quiet_hours_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="hostname_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("reverse_dns", "Reverse DNS"),
                    ("mdns", "mDNS"),
                    ("llmnr", "LLMNR"),
                    ("netbios", "NetBIOS"),
                    ("ssdp", "SSDP / UPnP"),
                    ("snmp", "SNMP"),
                    ("http", "Device web interface"),
                    ("arp", "ARP"),
                    ("manuf", "Wireshark manuf"),
                    ("inferred", "Inferred"),
                    ("imported", "Imported inventory"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="device",
            name="vendor_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("reverse_dns", "Reverse DNS"),
                    ("mdns", "mDNS"),
                    ("llmnr", "LLMNR"),
                    ("netbios", "NetBIOS"),
                    ("ssdp", "SSDP / UPnP"),
                    ("snmp", "SNMP"),
                    ("http", "Device web interface"),
                    ("arp", "ARP"),
                    ("manuf", "Wireshark manuf"),
                    ("inferred", "Inferred"),
                    ("imported", "Imported inventory"),
                ],
                default="",
                max_length=32,
            ),
        ),
    ]
