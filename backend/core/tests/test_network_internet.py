import uuid

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..database_writes import _PROCESS_WRITE_LOCK
from ..models import Device, NetworkInternetConnection, NetworkMapLayout, UserAccess
from ..network_map_commands import process_next_network_map_command


class NetworkInternetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('internet-admin', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.router = Device.objects.create(mac='aa:bb:cc:dd:ee:01', ip='192.168.1.1', role='router')
        self.other = Device.objects.create(mac='aa:bb:cc:dd:ee:02', ip='192.168.1.2', role='router')

    def enqueue(self, body, method='PUT'):
        return self.client.post('/api/v1/network-map/commands/', {
            'request_id': str(uuid.uuid4()), 'path': 'internet/', 'method': method, 'body': body,
        }, format='json')

    def create_uplink(self, target=None):
        self.assertEqual(self.enqueue({'target': target or self.router.pk, 'kind': 'ethernet', 'revision': 0}).status_code, 202)
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        return NetworkInternetConnection.objects.get()

    def test_get_has_no_write_side_effect_and_internet_never_creates_fake_device(self):
        self.assertIsNone(self.client.get('/api/v1/network-map/').data['data']['internet'])
        self.assertFalse(NetworkInternetConnection.objects.exists())
        uplink = self.create_uplink()
        data = self.client.get('/api/v1/network-map/').data['data']
        self.assertEqual(data['internet'], {'enabled': True, 'target': self.router.pk,
                                           'target_device': self.router.pk, 'kind': 'ethernet', 'revision': 1})
        self.assertEqual(Device.objects.count(), 2)
        self.assertFalse(NetworkMapLayout.objects.exists())
        self.assertTrue(uplink.enabled)

    def test_edit_remove_recreate_and_stale_revisions_never_overwrite(self):
        self.create_uplink()
        self.enqueue({'target': self.other.pk, 'kind': 'wifi', 'revision': 0})
        self.assertEqual(process_next_network_map_command().result['status_code'], 409)
        self.assertEqual(NetworkInternetConnection.objects.get().target_id, self.router.pk)
        self.enqueue({'revision': 1}, 'DELETE')
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        uplink = NetworkInternetConnection.objects.get()
        self.assertFalse(uplink.enabled)
        self.assertEqual(uplink.revision, 2)
        self.enqueue({'target': self.other.pk, 'kind': 'wifi', 'revision': 2})
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.enqueue({'revision': 1}, 'DELETE')
        self.assertEqual(process_next_network_map_command().result['status_code'], 409)
        uplink.refresh_from_db()
        self.assertTrue(uplink.enabled)
        self.assertEqual(uplink.target_id, self.other.pk)
        self.assertEqual(uplink.kind, 'wifi')
        self.assertEqual(Device.objects.count(), 2)

    def test_merged_interface_is_resolved_and_unavailable_targets_are_not_guessed(self):
        nic = Device.objects.create(mac='aa:bb:cc:dd:ee:03', ip='192.168.1.3', merged_into=self.router)
        self.create_uplink(nic.pk)
        data = self.client.get('/api/v1/network-map/').data['data']['internet']
        self.assertEqual(data['target'], nic.pk)
        self.assertEqual(data['target_device'], self.router.pk)
        self.router.archived = True
        self.router.save()
        self.assertIsNone(self.client.get('/api/v1/network-map/').data['data']['internet']['target_device'])
        nic.delete()
        uplink = NetworkInternetConnection.objects.get()
        self.assertIsNone(uplink.target_id)
        self.assertTrue(uplink.enabled)

    def test_scan_lock_defers_internet_change_and_virtual_position_saves(self):
        _PROCESS_WRITE_LOCK.acquire()
        try:
            self.assertEqual(self.enqueue({'target': self.router.pk, 'kind': 'unknown', 'revision': 0}).status_code, 202)
            self.assertIsNone(process_next_network_map_command())
            self.assertFalse(NetworkInternetConnection.objects.exists())
        finally:
            _PROCESS_WRITE_LOCK.release()
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        response = self.client.put('/api/v1/network-map/layout/', {'revision': 0, 'positions': {'internet': {'x': 100, 'y': 20}}}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NetworkMapLayout.objects.get().positions['internet']['x'], 100)

    def test_permissions_and_invalid_target_are_checked_at_execution(self):
        user = User.objects.create_user('internet-editor')
        self.client.force_authenticate(user)
        self.enqueue({'target': self.router.pk, 'kind': 'ethernet', 'revision': 0})
        UserAccess.objects.create(user=user, can_edit_devices=False)
        self.assertEqual(process_next_network_map_command().result['status_code'], 403)
        self.assertEqual(self.enqueue({'target': self.router.pk, 'revision': 0}).status_code, 403)
        self.assertFalse(NetworkInternetConnection.objects.exists())
        self.client.force_authenticate(self.user)
        self.enqueue({'target': self.router.pk, 'kind': 'ethernet', 'revision': 0})
        self.router.archived = True
        self.router.save()
        self.assertEqual(process_next_network_map_command().result['status_code'], 400)
        self.assertFalse(NetworkInternetConnection.objects.exists())
        self.assertEqual(APIClient().put('/api/v1/network-map/internet/', {}, format='json').status_code, 401)
