import uuid
import sqlite3
import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.db import connection, OperationalError
from rest_framework.test import APIClient

from ..database_writes import _PROCESS_WRITE_LOCK
from ..models import Device, NetworkLink, NetworkLinkDismissal, NetworkMapCommand, NetworkMapLayout, UserAccess
from ..network_map_commands import process_next_network_map_command


class NetworkMapCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('queue-admin', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.router = Device.objects.create(name='Router', mac='aa:bb:cc:dd:ee:10', ip='192.168.1.1', role='router')
        self.phone = Device.objects.create(name='Phone', mac='aa:bb:cc:dd:ee:20', ip='192.168.1.2', role='phone')

    def submit(self, path='links/', method='POST', body=None, request_id=None):
        return self.client.post('/api/v1/network-map/commands/', {
            'request_id': str(request_id or uuid.uuid4()), 'path': path, 'method': method,
            'body': body if body is not None else {'source': self.router.pk, 'target': self.phone.pk, 'kind': 'wifi'},
        }, format='json')

    def test_accept_during_scan_then_apply_once_after_lock_release(self):
        key = uuid.uuid4()
        _PROCESS_WRITE_LOCK.acquire()
        try:
            response = self.submit(request_id=key)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.data['data']['command']['status'], 'queued')
            self.assertEqual(response.data['data']['command']['pending_interfaces'], [self.router.pk, self.phone.pk])
            self.assertFalse(NetworkLink.objects.exists())
            self.assertIsNone(process_next_network_map_command())
            self.assertEqual(self.submit(request_id=key).data['data']['command']['id'], response.data['data']['command']['id'])
        finally:
            _PROCESS_WRITE_LOCK.release()
        job = process_next_network_map_command()
        self.assertEqual(job.status, 'succeeded')
        self.assertEqual(NetworkLink.objects.count(), 1)
        self.assertIsNone(process_next_network_map_command())
        self.assertEqual(self.submit(request_id=key).data['data']['command']['status'], 'succeeded')
        self.assertEqual(NetworkMapCommand.objects.count(), 1)

    def test_duplicate_request_id_cannot_change_payload(self):
        key = uuid.uuid4()
        self.submit(request_id=key)
        self.assertEqual(self.submit(body={}, request_id=key).status_code, 409)
        self.assertEqual(NetworkMapCommand.objects.count(), 1)

    def test_saved_connections_and_layout_edits_deletes_use_existing_validation(self):
        self.submit()
        process_next_network_map_command()
        link = NetworkLink.objects.get()
        self.submit(f'links/{link.pk}/', 'PUT', {'source': self.router.pk, 'target': self.phone.pk, 'kind': 'ethernet', 'revision': 1})
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        link.refresh_from_db()
        self.assertEqual(link.kind, 'ethernet')
        self.assertEqual(link.revision, 2)
        self.submit(f'links/{link.pk}/', 'DELETE', {'revision': 1})
        failed = process_next_network_map_command()
        self.assertEqual(failed.status, 'failed')
        self.assertEqual(failed.result['status_code'], 409)
        self.assertTrue(NetworkLink.objects.exists())
        self.submit(f'links/{link.pk}/', 'DELETE', {'revision': 2})
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertFalse(NetworkLink.objects.exists())

    def test_bulk_failure_is_atomic_and_does_not_block_following_jobs(self):
        self.submit('links/bulk/', body={'connections': [
            {'source': self.router.pk, 'target': self.phone.pk},
            {'source': self.router.pk, 'target': self.router.pk},
        ]})
        self.submit()
        self.assertEqual(process_next_network_map_command().status, 'failed')
        self.assertFalse(NetworkLink.objects.exists())
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertEqual(NetworkLink.objects.count(), 1)

    def test_unexpected_failure_rolls_back_and_does_not_poison_queue(self):
        self.submit()
        def crash(*args, **kwargs):
            NetworkMapLayout.objects.create(pk=1)
            raise RuntimeError('test')
        with patch.dict('core.network_map_commands.HANDLERS', {'network_links': crash}):
            self.assertEqual(process_next_network_map_command().status, 'failed')
        self.assertFalse(NetworkMapLayout.objects.exists())

    def test_canonical_layout_retains_hidden_positions_and_checks_revisions(self):
        NetworkMapLayout.objects.create(positions={str(self.phone.pk): {'x': 9999, 'y': 9999}})
        body = {'mode': 'infrastructure', 'revision': 0, 'positions': {str(self.router.pk): {'x': 40, 'y': 60}}}
        self.submit('layout/', 'PUT', body)
        self.submit('layout/', 'PUT', body)
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertEqual(process_next_network_map_command().result['status_code'], 409)
        layout = NetworkMapLayout.objects.get()
        self.assertEqual(layout.positions[str(self.phone.pk)]['x'], 9999)
        self.assertEqual(layout.positions[str(self.router.pk)]['x'], 40)
        self.assertEqual(layout.revision, 1)

    def test_owner_only_history_and_permissions_rechecked_at_execution(self):
        user = User.objects.create_user('editor')
        self.client.force_authenticate(user)
        self.submit()
        access = UserAccess.objects.create(user=user, can_edit_devices=False)
        self.assertEqual(process_next_network_map_command().result['status_code'], 403)
        self.assertFalse(NetworkLink.objects.exists())
        self.assertEqual(self.submit().status_code, 403)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/v1/network-map/commands/').data['data']['commands'], [])
        access.can_edit_home_map = True
        access.save()
        self.client.force_authenticate(user)
        self.assertEqual(self.submit('layout/', 'PUT', {'revision': 0, 'positions': {}}).status_code, 202)

    def test_deleted_devices_fail_safely_and_payloads_are_bounded(self):
        self.submit()
        self.phone.delete()
        self.assertEqual(process_next_network_map_command().status, 'failed')
        self.assertFalse(NetworkLink.objects.exists())
        self.assertEqual(self.submit('../settings/').status_code, 400)
        self.assertEqual(self.submit(body=[]).status_code, 400)
        self.assertEqual(APIClient().get('/api/v1/network-map/commands/').status_code, 401)

    def test_new_inventory_fields_for_mobile_display(self):
        device = self.client.get('/api/v1/network-map/').data['data']['devices'][0]
        self.assertIn('last_seen', device)
        self.assertIn('is_gateway', device)

    def test_queue_capacity_and_history_keep_all_pending_requests(self):
        from django.utils import timezone
        NetworkMapCommand.objects.bulk_create([
            NetworkMapCommand(requested_by=self.user, request_id=uuid.uuid4(), path='links/', method='POST')
            for _ in range(100)
        ])
        NetworkMapCommand.objects.bulk_create([
            NetworkMapCommand(requested_by=self.user, request_id=uuid.uuid4(), path='links/', method='POST',
                              status='succeeded', finished_at=timezone.now())
            for _ in range(110)
        ])
        self.assertEqual(self.submit().status_code, 429)
        self.assertEqual(NetworkMapCommand.objects.filter(status='queued').count(), 100)
        jobs = self.client.get('/api/v1/network-map/commands/').data['data']['commands']
        self.assertEqual(len(jobs), 200)
        self.assertEqual(sum(job['status'] == 'queued' for job in jobs), 100)

    def test_malformed_layout_is_rejected_before_it_can_replace_a_browser_draft(self):
        response = self.submit('layout/', 'PUT', {'revision': 0, 'positions': 'bad'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NetworkMapCommand.objects.exists())

    def test_virtual_group_positions_are_saved_without_creating_fake_devices(self):
        positions = {f'mobile-{self.router.pk}-wifi': {'x': 100, 'y': 200}, 'mobile-unassigned': {'x': 400, 'y': 200}}
        self.assertEqual(self.submit('layout/', 'PUT', {'positions': positions, 'revision': 0}).status_code, 202)
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertEqual(NetworkMapLayout.objects.get().positions, positions)
        self.assertEqual(Device.objects.count(), 2)
        self.assertEqual(self.submit('layout/', 'PUT', {'positions': {'mobile-999999-wifi': {'x': 0, 'y': 0}}, 'revision': 1}).status_code, 400)

    def test_lldp_review_actions_are_queued_and_revalidate_current_observations(self):
        from django.utils import timezone
        self.router.snmp_data = {'neighbors': [{'local_port': 'eth0', 'chassis_id': self.phone.mac, 'port_id': 'eth1'}]}
        self.router.snmp_last_seen = timezone.now()
        self.router.save()
        key = self.client.get('/api/v1/network-map/').data['data']['suggestions'][0]['key']
        self.assertEqual(self.submit(f'suggestions/{key}/dismiss/', body={}).status_code, 202)
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertTrue(NetworkLinkDismissal.objects.filter(pk=key).exists())
        self.submit('suggestions/restored/', 'DELETE', {})
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertFalse(NetworkLinkDismissal.objects.exists())
        self.submit(f'suggestions/{key}/accept/', body={})
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertEqual(NetworkLink.objects.get().origin, 'lldp')
        NetworkLink.objects.all().delete()
        self.submit(f'suggestions/{key}/accept/', body={})
        self.phone.archived = True
        self.phone.save()
        self.assertEqual(process_next_network_map_command().result['status_code'], 409)
        self.assertFalse(NetworkLink.objects.exists())


class NetworkMapQueueContentionTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'sqlite':
            self.skipTest('SQLite-specific contention checks')
        self.user = User.objects.create_user('queue-contention', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        database = str(connection.settings_dict['NAME'])
        self.blocker = sqlite3.connect(database, uri=database.startswith('file:'), isolation_level=None)
        self.addCleanup(self.blocker.close)

    def submit(self):
        return self.client.post('/api/v1/network-map/commands/', {
            'request_id': str(uuid.uuid4()), 'path': 'layout/', 'method': 'PUT',
            'body': {'revision': 0, 'positions': {}, 'mode': 'infrastructure'},
        }, format='json')

    def test_transient_sqlite_contention_accepts_after_retry(self):
        self.blocker.execute('BEGIN IMMEDIATE')
        self.blocker.execute('UPDATE core_networkmapcommand SET status = status')
        try:
            with patch('core.views.network_map.time.sleep', side_effect=lambda _: self.blocker.rollback()):
                response = self.submit()
            self.assertEqual(response.status_code, 202)
        finally:
            self.blocker.rollback()
        self.assertEqual(process_next_network_map_command().status, 'succeeded')

    def test_real_sqlite_lock_never_claims_unpersisted_request_is_accepted(self):
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA busy_timeout')
            timeout = cursor.fetchone()[0]
        self.blocker.execute('BEGIN IMMEDIATE')
        self.blocker.execute('UPDATE core_networkmapcommand SET status = status')
        try:
            start = time.monotonic()
            response = self.submit()
            self.assertLess(time.monotonic() - start, 3)
            self.assertEqual(response.status_code, 503)
        finally:
            self.blocker.rollback()
        self.assertFalse(NetworkMapCommand.objects.exists())
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA busy_timeout')
            self.assertEqual(cursor.fetchone()[0], timeout)

    def test_crash_before_completion_leaves_command_queued_and_changes_rolled_back(self):
        self.submit()
        def interrupted(*args, **kwargs):
            NetworkMapLayout.objects.create(pk=1)
            raise OperationalError('database is locked')
        with patch.dict('core.network_map_commands.HANDLERS', {'network_layout': interrupted}):
            self.assertIsNone(process_next_network_map_command())
        self.assertFalse(NetworkMapLayout.objects.exists())
        self.assertEqual(NetworkMapCommand.objects.get().status, 'queued')
        connection.close()
        self.assertEqual(process_next_network_map_command().status, 'succeeded')
        self.assertEqual(NetworkMapLayout.objects.get().revision, 1)


class SingleNetworkMapMigrationTests(TransactionTestCase):
    def test_upgrade_consolidates_layouts_without_changing_connections(self):
        from django.db.migrations.executor import MigrationExecutor
        from ..network_map import link_signature
        executor = MigrationExecutor(connection)
        executor.migrate([('core', '0057_network_map_background_commands')])
        try:
            apps = executor.loader.project_state([('core', '0057_network_map_background_commands')]).apps
            OldDevice = apps.get_model('core', 'Device')
            OldLink = apps.get_model('core', 'NetworkLink')
            OldLayout = apps.get_model('core', 'NetworkMapLayout')
            first = OldDevice.objects.create(mac='aa:bb:cc:dd:ee:11', ip='192.168.1.1')
            second = OldDevice.objects.create(mac='aa:bb:cc:dd:ee:22', ip='192.168.1.2')
            OldLink.objects.create(source_id=first.pk, target_id=second.pk, kind='wifi', signature=link_signature(first.pk, second.pk))
            OldLayout.objects.create(pk=1, positions={str(first.pk): {'x': 9999, 'y': 9999}}, revision=3)
            OldLayout.objects.create(pk=2, positions={}, infrastructure_positions={str(first.pk): {'x': 40, 'y': 80}}, revision=5)
        finally:
            latest = MigrationExecutor(connection)
            latest.migrate(latest.loader.graph.leaf_nodes('core'))
        self.assertEqual(NetworkMapLayout.objects.get(pk=1).positions, {})
        self.assertEqual(NetworkMapLayout.objects.get(pk=1).revision, 4)
        self.assertEqual(NetworkMapLayout.objects.get(pk=2).positions, {str(first.pk): {'x': 40, 'y': 80}})
        self.assertEqual(NetworkLink.objects.get().kind, 'wifi')
        self.assertEqual(Device.objects.count(), 2)
