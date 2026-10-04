from types import SimpleNamespace

from django.test import SimpleTestCase

from ..port_guidance import PORT_CATALOG, port_guidance

class PortGuidanceCatalogTests(SimpleTestCase):
    def test_catalog_covers_initial_guidance_ports(self):
        required_ports = {
            21,
            53,
            80,
            135,
            139,
            443,
            445,
            515,
            548,
            554,
            631,
            873,
            1883,
            2049,
            3389,
            5000,
            5001,
            5555,
            5900,
            8080,
            8123,
            8443,
            8883,
            9100,
        }

        self.assertTrue(
            required_ports.issubset(
                {port for protocol, port in PORT_CATALOG if protocol == "tcp"}
            )
        )

    def test_known_printer_gets_expected_printing_guidance(self):
        device = SimpleNamespace(known=True, role="printer", icon="printer")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 9100, "service": "jetdirect"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "RAW printing")

    def test_known_nas_gets_expected_file_sharing_guidance(self):
        device = SimpleNamespace(known=True, role="nas", icon="nas")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 445, "service": "microsoft-ds"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "SMB")

    def test_known_gateway_gets_expected_dns_guidance(self):
        device = SimpleNamespace(known=True, role="gateway", icon="router")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 53, "service": "domain"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "DNS")

    def test_netbios_guidance_recommends_disabling_legacy_service(self):
        device = SimpleNamespace(known=True, role="computer", icon="desktop")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 139, "service": "netbios-ssn"},
        )

        self.assertEqual(guidance["recommendation"], "usually_disable")
        self.assertEqual(guidance["service_name"], "NetBIOS Session Service")

    def test_android_debug_bridge_guidance_recommends_disabling_service(self):
        device = SimpleNamespace(known=True, role="streamer", icon="tv")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 5555, "service": "freeciv"},
        )

        self.assertEqual(guidance["recommendation"], "usually_disable")
        self.assertEqual(guidance["service_name"], "Android Debug Bridge")

    def test_known_home_automation_hub_gets_expected_mqtt_guidance(self):
        device = SimpleNamespace(known=True, role="hub", icon="smart-hub")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 1883, "service": "mqtt"},
        )

        self.assertEqual(guidance["recommendation"], "expected")
        self.assertEqual(guidance["service_name"], "MQTT")

    def test_unknown_catalog_port_gets_generic_non_definitive_guidance(self):
        device = SimpleNamespace(known=True, role="device", icon="unknown")

        guidance = port_guidance(
            device,
            {"protocol": "tcp", "port": 12345, "service": ""},
        )

        self.assertEqual(guidance["recommendation"], "review")
        self.assertEqual(guidance["service_name"], "Unidentified service")
        self.assertIn("not enough", guidance["context"])
