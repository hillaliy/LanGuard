from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Device, DevicePort, NetworkEvent, UserAccess
from .notifications import notification_event_allowed
from .scan import sync_discovered_device, mark_missing_devices_offline
from .views import import_inventory_devices


class DeviceArchiveTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('archive-admin', is_staff=True)
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(name='Old router', mac='aa:bb:cc:dd:ee:01', ip='192.168.1.10')
        self.event = NetworkEvent.objects.create(device=self.device, event_type='device_offline', message='Offline')
        DevicePort.objects.create(device=self.device, port=80, open=True)

    def test_archive_preserves_history_and_excludes_active_lists_and_counters(self):
        response = self.client.put(f'/api/v1/device/?id={self.device.id}', {'archived': True}, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertTrue(Device.objects.get(pk=self.device.pk).archived)
        self.assertTrue(NetworkEvent.objects.filter(pk=self.event.pk).exists())
        self.assertEqual(self.device.ports.count(), 1)
        active = self.client.get('/api/v1/device/').data
        self.assertEqual(active['data'], [])
        self.assertEqual(active['counters']['all_devices'], 0)
        self.assertEqual(active['counters']['open_ports'], 0)
        status = self.client.get('/api/v1/scan/status/').data
        self.assertEqual(status['counters']['all_devices'], 0)
        archived = self.client.get('/api/v1/device/', {'archived': 'true'}).data
        self.assertEqual([d['id'] for d in archived['data']], [self.device.id])
        detail = self.client.get('/api/v1/device/', {'id': self.device.id}).data
        self.assertTrue(detail['data']['archived'])

    def test_restore_and_permissions(self):
        self.device.archived = True
        self.device.save()
        user = User.objects.create_user('reader')
        UserAccess.objects.create(user=user, can_edit_devices=False)
        self.client.force_authenticate(user)
        url = f'/api/v1/device/?id={self.device.id}'
        self.assertEqual(self.client.put(url, {'archived': False}, format='json').status_code, 403)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.put(url, {'archived': False}, format='json').status_code, 202)
        self.assertEqual(len(self.client.get('/api/v1/device/').data['data']), 1)

    @override_settings(PORT_SCAN_ENABLED=False)
    @patch('core.scan.get_hostname', return_value=('', ''))
    @patch('core.scan.manuf_vendor', return_value='')
    @patch('core.scan.notify_event')
    def test_rediscovery_restores_same_device(self, notify, vendor, hostname):
        self.device.archived = True
        self.device.online = False
        self.device.save()
        result = sync_discovered_device((None, SimpleNamespace(psrc=self.device.ip, hwsrc=self.device.mac)))
        self.device.refresh_from_db()
        self.assertFalse(self.device.archived)
        self.assertTrue(self.device.online)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(result['new_devices'], 0)
        self.assertTrue(NetworkEvent.objects.filter(pk=self.event.pk).exists())

    def test_archived_missing_device_is_not_probed_or_notified(self):
        self.device.archived = True
        self.device.online = True
        self.device.offline_notification_preference = 'always'
        self.device.save()
        with patch('core.scan.keep_online_if_ports_respond') as probe:
            mark_missing_devices_offline([])
        probe.assert_not_called()
        self.event.refresh_from_db()
        self.assertFalse(notification_event_allowed(self.event))
        self.device.refresh_from_db()
        self.assertEqual(self.device.missed_scans, 0)

    def test_export_import_preserves_archive_and_old_import_does_not_reset_it(self):
        self.device.archived = True
        self.device.save()
        payload = self.client.get('/api/v1/devices/export/').json()
        self.device.archived = False
        self.device.save()
        import_inventory_devices(payload)
        self.device.refresh_from_db()
        self.assertTrue(self.device.archived)
        import_inventory_devices({'devices': [{'mac': self.device.mac, 'ip': self.device.ip}]})
        self.device.refresh_from_db()
        self.assertTrue(self.device.archived)
