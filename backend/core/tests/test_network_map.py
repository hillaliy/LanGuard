from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import Device, NetworkLink, NetworkLinkDismissal, NetworkMapLayout, UserAccess
from ..network_map import record_network_observations
from ..serializers.network_map import NetworkLayoutSerializer


class NetworkMapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("map-admin", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.router = Device.objects.create(name="Router", mac="aa:bb:cc:dd:ee:10", ip="192.168.1.1", role="router")
        self.switch = Device.objects.create(name="Switch", mac="aa:bb:cc:dd:ee:20", ip="192.168.1.2", role="switch")
        self.laptop = Device.objects.create(name="Laptop", mac="aa:bb:cc:dd:ee:30", ip="192.168.1.3")

    def get_map(self):
        response = self.client.get("/api/v1/network-map/")
        self.assertEqual(response.status_code, 200)
        return response.data["data"]

    def create_link(self, **overrides):
        body = {"source": self.router.pk, "target": self.switch.pk, "kind": "ethernet",
                "source_port": "LAN 1", "target_port": "eth0", **overrides}
        return self.client.post("/api/v1/network-map/links/", body, format="json")

    def report_neighbor(self, **overrides):
        self.router.snmp_data = {"neighbors": [{"local_port": "LAN 1", "chassis_id": self.switch.mac,
                                                 "port_id": "eth0", "system_name": "Switch", **overrides}]}
        self.router.snmp_last_seen = timezone.now()
        self.router.save(update_fields=["snmp_data", "snmp_last_seen"])
        return self.get_map()["suggestions"]

    def test_authentication_required_and_get_has_no_write_side_effects(self):
        self.assertEqual(APIClient().get("/api/v1/network-map/").status_code, 401)
        self.get_map()
        self.assertEqual(NetworkMapLayout.objects.count(), 0)
        self.assertEqual(NetworkLink.objects.count(), 0)
        self.assertEqual(NetworkLinkDismissal.objects.count(), 0)

    def test_manual_connection_round_trip(self):
        response = self.create_link()
        self.assertEqual(response.status_code, 200)
        link = self.get_map()["links"][0]
        self.assertEqual(link["source_device"], self.router.pk)
        self.assertEqual(link["target_device"], self.switch.pk)
        self.assertEqual(link["origin"], "manual")
        self.assertFalse(link["stale"])

    def test_reversed_duplicate_connection_is_rejected(self):
        self.create_link()
        response = self.create_link(source=self.switch.pk, target=self.router.pk, source_port="eth0", target_port="LAN 1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(NetworkLink.objects.count(), 1)

    def test_parallel_links_and_physical_cycles_are_allowed(self):
        self.assertEqual(self.create_link().status_code, 200)
        self.assertEqual(self.create_link(source_port="LAN 2", target_port="eth1").status_code, 200)
        self.assertEqual(self.create_link(source=self.switch.pk, target=self.laptop.pk).status_code, 200)
        self.assertEqual(self.create_link(source=self.laptop.pk, target=self.router.pk).status_code, 200)
        self.assertEqual(len(self.get_map()["links"]), 4)

    def test_invalid_connections_are_rejected(self):
        for body in ({"target": self.router.pk}, {"kind": "script"}, {"source_port": "x" * 129}, {"target": 99999}):
            with self.subTest(body=body):
                self.assertEqual(self.create_link(**body).status_code, 400)

    def test_archived_and_visitor_endpoints_are_excluded(self):
        self.switch.known = True
        self.switch.save(update_fields=["known"])
        for field in ("archived", "is_visitor"):
            setattr(self.switch, field, True)
            self.switch.save(update_fields=[field])
            self.assertEqual(self.create_link().status_code, 400)
            self.assertNotIn(self.switch.pk, [item["id"] for item in self.get_map()["devices"]])
            setattr(self.switch, field, False)
            self.switch.save(update_fields=[field])

    def test_interfaces_are_grouped_without_duplicating_logical_devices(self):
        alias = Device.objects.create(mac="aa:bb:cc:dd:ee:40", ip="192.168.1.4", merged_into=self.laptop)
        self.assertEqual(self.create_link(target=alias.pk).status_code, 200)
        data = self.get_map()
        self.assertEqual(len(data["devices"]), 3)
        laptop = next(item for item in data["devices"] if item["id"] == self.laptop.pk)
        self.assertEqual(len(laptop["interfaces"]), 2)
        self.assertEqual(data["links"][0]["target"], alias.pk)
        self.assertEqual(data["links"][0]["target_device"], self.laptop.pk)
        self.assertEqual(self.create_link(source=self.laptop.pk, target=alias.pk).status_code, 400)

    def test_merge_and_unmerge_preserve_link_identity(self):
        self.create_link()
        link_id = NetworkLink.objects.get().pk
        self.switch.merged_into = self.router
        self.switch.save(update_fields=["merged_into"])
        self.assertEqual(self.get_map()["links"], [])
        self.assertEqual(self.get_map()["hidden_links"], 1)
        self.switch.merged_into = None
        self.switch.save(update_fields=["merged_into"])
        self.assertEqual(self.get_map()["links"][0]["id"], link_id)

    def test_edit_and_delete_require_current_revision(self):
        self.create_link()
        link = NetworkLink.objects.get()
        url = f"/api/v1/network-map/links/{link.pk}/"
        body = {"source": self.router.pk, "target": self.switch.pk, "label": "Uplink", "revision": 1}
        self.assertEqual(self.client.put(url, body, format="json").status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.source_port, "LAN 1")
        self.assertEqual(self.client.put(url, body, format="json").status_code, 409)
        self.assertEqual(self.client.delete(url, {"revision": 1}, format="json").status_code, 409)
        self.assertEqual(self.client.delete(url, {"revision": 2}, format="json").status_code, 200)
        self.assertFalse(NetworkLink.objects.exists())

    def test_layout_revision_prevents_silent_overwrites(self):
        url = "/api/v1/network-map/layout/"
        body = {"revision": 0, "positions": {str(self.router.pk): {"x": 10, "y": 20}}}
        self.assertEqual(self.client.put(url, body, format="json").status_code, 200)
        self.assertEqual(self.client.put(url, body, format="json").status_code, 409)
        self.assertEqual(self.get_map()["layout"]["positions"], body["positions"])

    def test_layout_retains_positions_for_temporarily_missing_devices(self):
        url = "/api/v1/network-map/layout/"
        self.client.put(url, {"revision": 0, "positions": {str(self.switch.pk): {"x": 30, "y": 40}}}, format="json")
        self.switch.archived = True
        self.switch.save(update_fields=["archived"])
        self.client.put(url, {"revision": 1, "positions": {str(self.router.pk): {"x": 0, "y": 0}}}, format="json")
        self.assertEqual(self.get_map()["layout"]["positions"][str(self.switch.pk)], {"x": 30, "y": 40})

    def test_layout_validation_rejects_nonfinite_or_malformed_positions(self):
        for positions in ([], {"x": {"x": 0, "y": 0}}, {"01": {"x": 0, "y": 0}},
                          {"9" * 50: {"x": 0, "y": 0}}, {"99999": {"x": 0, "y": 0}},
                          {str(self.router.pk): {"x": True, "y": 0}},
                          {str(self.router.pk): {"x": float("nan"), "y": 0}},
                          {str(self.router.pk): {"x": 0, "y": 1e8}}):
            with self.subTest(positions=positions):
                serializer = NetworkLayoutSerializer(data={"revision": 0, "positions": positions})
                self.assertFalse(serializer.is_valid())

    def test_lldp_is_suggested_without_creating_a_saved_link(self):
        suggestions = self.report_neighbor()
        self.assertEqual(len(suggestions), 1)
        self.assertFalse(NetworkLink.objects.exists())
        self.assertEqual(suggestions[0]["origin"], "lldp")
        self.assertFalse(suggestions[0]["stale"])

    def test_similar_or_exact_names_alone_do_not_create_connections(self):
        self.assertEqual(self.report_neighbor(chassis_id="Switch"), [])
        self.assertEqual(len(self.get_map()["unresolved"]), 1)
        self.assertEqual(self.report_neighbor(chassis_id="aa:bb:cc:dd:ee:ff"), [])

    def test_reciprocal_reports_are_deduplicated(self):
        self.report_neighbor()
        self.switch.snmp_data = {"neighbors": [{"local_port": "eth0", "chassis_id": self.router.mac, "port_id": "LAN 1"}]}
        self.switch.snmp_last_seen = timezone.now()
        self.switch.save(update_fields=["snmp_data", "snmp_last_seen"])
        self.assertEqual(len(self.get_map()["suggestions"]), 1)

    def test_acceptance_preserves_evidence_source_and_timestamp(self):
        key = self.report_neighbor()[0]["key"]
        response = self.client.post(f"/api/v1/network-map/suggestions/{key}/accept/")
        self.assertEqual(response.status_code, 200)
        data = self.get_map()
        self.assertEqual(len(data["links"]), 1)
        self.assertEqual(data["links"][0]["origin"], "lldp")
        self.assertIsNotNone(data["links"][0]["observed_at"])
        self.assertEqual(data["suggestions"], [])

    def test_disappeared_evidence_does_not_delete_accepted_connection(self):
        key = self.report_neighbor()[0]["key"]
        self.client.post(f"/api/v1/network-map/suggestions/{key}/accept/")
        self.router.snmp_data = {"neighbors": []}
        self.router.save(update_fields=["snmp_data"])
        link = self.get_map()["links"][0]
        self.assertTrue(link["stale"])
        self.assertFalse(link["currently_reported"])

    def test_evidence_older_than_a_day_is_explicitly_stale(self):
        self.report_neighbor()
        self.router.snmp_last_seen = timezone.now() - timedelta(days=2)
        self.router.save(update_fields=["snmp_last_seen"])
        self.assertTrue(self.get_map()["suggestions"][0]["stale"])

    def test_dismiss_restore_and_delete_do_not_recreate_links(self):
        key = self.report_neighbor()[0]["key"]
        self.assertEqual(self.client.post(f"/api/v1/network-map/suggestions/{key}/dismiss/").status_code, 200)
        self.assertEqual(self.get_map()["suggestions"], [])
        self.assertEqual(self.get_map()["dismissed_count"], 1)
        self.client.delete("/api/v1/network-map/suggestions/restored/")
        self.assertEqual(len(self.get_map()["suggestions"]), 1)
        self.client.post(f"/api/v1/network-map/suggestions/{key}/accept/")
        link = NetworkLink.objects.get()
        self.client.delete(f"/api/v1/network-map/links/{link.pk}/", {"revision": 1}, format="json")
        self.assertEqual(self.get_map()["suggestions"], [])
        self.assertFalse(NetworkLink.objects.exists())

    def test_manual_changes_cannot_be_overwritten_by_lldp(self):
        key = self.report_neighbor()[0]["key"]
        self.client.post(f"/api/v1/network-map/suggestions/{key}/accept/")
        link = NetworkLink.objects.get()
        body = {"source": self.router.pk, "target": self.laptop.pk, "kind": "wifi", "revision": 1,
                "origin": "lldp", "label": "User selected"}
        self.client.put(f"/api/v1/network-map/links/{link.pk}/", body, format="json")
        self.report_neighbor()
        record_network_observations()
        link.refresh_from_db()
        self.assertEqual(link.origin, "manual")
        self.assertEqual(link.target_id, self.laptop.pk)
        self.assertEqual(link.label, "User selected")

    def test_scanning_updates_evidence_time_without_changing_edit_revision(self):
        key = self.report_neighbor()[0]["key"]
        self.client.post(f"/api/v1/network-map/suggestions/{key}/accept/")
        link = NetworkLink.objects.get()
        original = link.observed_at
        self.report_neighbor()
        record_network_observations()
        link.refresh_from_db()
        self.assertGreater(link.observed_at, original)
        self.assertEqual(link.revision, 1)

    def test_unknown_or_missing_suggestions_cannot_be_accepted(self):
        for action in ("accept", "dismiss"):
            self.assertEqual(self.client.post(f"/api/v1/network-map/suggestions/missing/{action}/").status_code, 409)

    def test_permissions_separate_layout_from_connections(self):
        viewer = User.objects.create_user("viewer")
        access = UserAccess.objects.create(user=viewer, can_edit_devices=False, can_edit_home_map=False, can_run_scans=False)
        self.client.force_authenticate(viewer)
        self.assertEqual(self.client.get("/api/v1/network-map/").status_code, 200)
        self.assertEqual(self.create_link().status_code, 403)
        self.assertEqual(self.client.put("/api/v1/network-map/layout/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.delete("/api/v1/network-map/suggestions/restored/").status_code, 403)
        access.can_edit_home_map = True
        access.save()
        self.assertEqual(self.client.put("/api/v1/network-map/layout/", {"revision": 0, "positions": {}}, format="json").status_code, 200)
        self.assertEqual(self.create_link().status_code, 403)

    def test_device_deletion_removes_connections_without_dangling_endpoints(self):
        self.create_link()
        self.switch.delete()
        self.assertFalse(NetworkLink.objects.exists())
        self.assertEqual(self.get_map()["links"], [])
