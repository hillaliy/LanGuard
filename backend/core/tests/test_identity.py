
from django.test import TestCase

from ..models import (
    Device,
)
from ..serializers.devices import device_identity

class DeviceIdentityConfidenceTests(TestCase):
    def test_high_confidence_requires_strong_hostname_and_vendor_sources(self):
        device = Device.objects.create(
            name="Living room streamer",
            ip="192.168.1.20",
            mac="90:dd:5d:b7:bd:01",
            hostname="living room streamer",
            hostname_source=Device.IdentitySource.MDNS,
            vendor="Apple, Inc.",
            vendor_source=Device.IdentitySource.MANUF,
        )

        identity = device_identity(device)

        self.assertEqual(identity["confidence"], "high")
        self.assertEqual(identity["hostname_confidence"], "high")
        self.assertEqual(identity["vendor_confidence"], "high")
        self.assertEqual(
            [item["source_display"] for item in identity["evidence"]],
            ["mDNS", "Wireshark manuf"],
        )

    def test_unknown_legacy_sources_are_not_overstated(self):
        device = Device.objects.create(
            name="Imported device",
            ip="192.168.1.21",
            mac="90:dd:5d:b7:bd:02",
            vendor="Example vendor",
        )

        identity = device_identity(device)

        self.assertEqual(identity["confidence"], "low")
        self.assertEqual(identity["vendor_confidence"], "low")
