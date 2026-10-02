import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Divider, Group, Image, LoadingOverlay, Modal, Paper, PasswordInput,
  SimpleGrid, Stack, Switch, Text, TextInput, Title, UnstyledButton,
} from '@mantine/core';
import { IconAlertCircle, IconShieldCheck, IconUserEdit, IconUserMinus, IconUserPlus } from '@tabler/icons-react';
import { apiRequest, clearStoredUser, storeUser } from '../api';
import authClasses from '../auth.module.css';
import { showErrorNotification, showServerNotification } from '../utils/notifications';
import { capitalizeName, userDisplayName } from './user';

export function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function loadSetupStatus() {
      try {
        const payload = await apiRequest('setup/');
        if (mounted) {
          setRegistrationOpen(Boolean(payload.registration_open));
          if (!payload.registration_open) {
            setMode('login');
          }
        }
      } catch {
        if (mounted) {
          setRegistrationOpen(false);
          setMode('login');
        }
      }
    }

    loadSetupStatus();
    return () => {
      mounted = false;
    };
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'register') {
        await apiRequest('register/', {
          method: 'POST',
          body: {
            username,
            password,
            password_confirm: passwordConfirm,
          },
        });
      }

      const user = await apiRequest('login/', {
        method: 'POST',
        body: { username, password },
      });
      storeUser(user);
      showServerNotification(user);
      onLogin(user);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={authClasses.shell}>
      <Paper className={authClasses.panel} p="xl">
        <LoadingOverlay visible={loading} />
        <Stack gap="lg">
          <Group gap="sm">
            <Image src="/logo.png" alt="LanGuard" w={48} h={48} radius="sm" />
            <Box>
              <Title order={2}>LanGuard</Title>
              <Text size="sm" c="dimmed">
                Home network visibility
              </Text>
            </Box>
          </Group>

          {error && (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>
              {error}
            </Alert>
          )}

          <form onSubmit={submit}>
            <Stack>
              <TextInput
                label="Username"
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
                leftSection={<IconShieldCheck size={18} />}
                required
              />
              <PasswordInput
                label="Password"
                value={password}
                onChange={(event) => setPassword(event.currentTarget.value)}
                required
              />
              {mode === 'register' && (
                <PasswordInput
                  label="Confirm password"
                  value={passwordConfirm}
                  onChange={(event) =>
                    setPasswordConfirm(event.currentTarget.value)
                  }
                  required
                />
              )}
              <Button type="submit" leftSection={<IconShieldCheck size={18} />}>
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </Button>
            </Stack>
          </form>

          {registrationOpen && (
            <Button
              variant="subtle"
              leftSection={<IconUserPlus size={18} />}
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            >
              {mode === 'login' ? 'Create first user' : 'Use existing account'}
            </Button>
          )}
        </Stack>
      </Paper>
    </main>
  );
}

export function UserManagementModal({ opened, onClose, currentUser, onCurrentUserUpdated }) {
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('new');
  const [username, setUsername] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [isStaff, setIsStaff] = useState(false);
  const [canEditDevices, setCanEditDevices] = useState(true);
  const [canEditHomeMap, setCanEditHomeMap] = useState(true);
  const [canRunScans, setCanRunScans] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);

  const selectedUser = selectedUserId === 'new'
    ? null
    : users.find((item) => String(item.id) === String(selectedUserId));
  const canManageUsers = Boolean(currentUser?.is_staff || currentUser?.is_superuser);
  const adminUserCount = users.filter((item) => item.is_staff).length;
  const selectedUserIsLastAdmin = Boolean(selectedUser?.is_staff && adminUserCount <= 1);

  async function loadUsers() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiRequest('users/');
      const nextUsers = payload.data || [];
      setUsers(nextUsers);
      if (!canManageUsers && nextUsers[0]) {
        setSelectedUserId(String(nextUsers[0].id));
      } else if (selectedUserId !== 'new' && !nextUsers.some((item) => String(item.id) === String(selectedUserId))) {
        setSelectedUserId('new');
      }
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (opened) {
      loadUsers();
    }
  }, [opened]);

  useEffect(() => {
    if (selectedUser) {
      setUsername(selectedUser.username || '');
      setFirstName(selectedUser.first_name || '');
      setLastName(selectedUser.last_name || '');
      setIsActive(Boolean(selectedUser.is_active));
      setIsStaff(Boolean(selectedUser.is_staff));
      setCanEditDevices(Boolean(selectedUser.can_edit_devices));
      setCanEditHomeMap(Boolean(selectedUser.can_edit_home_map));
      setCanRunScans(Boolean(selectedUser.can_run_scans));
    } else {
      setUsername('');
      setFirstName('');
      setLastName('');
      setIsActive(true);
      setIsStaff(false);
      setCanEditDevices(true);
      setCanEditHomeMap(true);
      setCanRunScans(true);
    }
    setPassword('');
    setPasswordConfirm('');
    setError('');
  }, [selectedUserId, selectedUser?.id]);

  async function saveUser() {
    setSaving(true);
    setError('');
    try {
      const body = {
        username,
        first_name: capitalizeName(firstName),
        last_name: capitalizeName(lastName),
        is_active: isActive,
        is_staff: isStaff,
        can_edit_devices: isStaff || canEditDevices,
        can_edit_home_map: isStaff || canEditHomeMap,
        can_run_scans: isStaff || canRunScans,
        ...(password ? { password, password_confirm: passwordConfirm } : {}),
      };
      const saved = selectedUser
        ? await apiRequest(`users/?id=${selectedUser.id}`, { method: 'PUT', body })
        : await apiRequest('users/', { method: 'POST', body });
      const savedUser = saved.data;

      await loadUsers();
      setSelectedUserId(String(savedUser.id));
      showServerNotification(saved);

      if (currentUser?.username === selectedUser?.username) {
        if (savedUser.is_active) {
          onCurrentUserUpdated({
            ...currentUser,
            id: savedUser.id,
            username: savedUser.username,
            first_name: savedUser.first_name,
            last_name: savedUser.last_name,
            is_staff: savedUser.is_staff,
            can_edit_devices: savedUser.can_edit_devices,
            can_edit_home_map: savedUser.can_edit_home_map,
            can_run_scans: savedUser.can_run_scans,
          });
        } else {
          clearStoredUser();
          onCurrentUserUpdated(null);
        }
      }
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  async function deleteUser() {
    if (!deleteTarget) {
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload = await apiRequest(`users/?id=${deleteTarget.id}`, { method: 'DELETE' });
      await loadUsers();
      setSelectedUserId('new');
      showServerNotification(payload);
      if (currentUser?.username === deleteTarget.username) {
        clearStoredUser();
        onCurrentUserUpdated(null);
      }
      setDeleteTarget(null);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  function closeModal() {
    setDeleteTarget(null);
    onClose();
  }

  return (
    <>
      <Modal opened={opened} onClose={closeModal} title={canManageUsers ? 'Users' : 'My account'} centered size="lg">
        <LoadingOverlay visible={loading} />
        <Stack>
          {error && (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>
              {error}
            </Alert>
          )}
          <SimpleGrid cols={{ base: 1, sm: canManageUsers ? 2 : 1 }}>
            {canManageUsers && (
              <Box className="user-list-panel">
                <Group justify="space-between" mb="sm">
                  <Text fw={700}>Accounts</Text>
                  <Button
                    size="xs"
                    variant="light"
                    leftSection={<IconUserPlus size={15} />}
                    onClick={() => setSelectedUserId('new')}
                  >
                    New
                  </Button>
                </Group>
                <Stack gap="xs">
                  {users.map((item) => (
                    <UnstyledButton
                      key={item.id}
                      className={`user-list-button ${String(item.id) === String(selectedUserId) ? 'active' : ''}`}
                      onClick={() => setSelectedUserId(String(item.id))}
                    >
                      <Group gap="xs" wrap="nowrap">
                        <IconUserEdit size={17} />
                        <Box ta="start" className="truncate-cell">
                          <Text size="sm" fw={700}>{userDisplayName(item)}</Text>
                          <Text size="xs" c="dimmed">
                            {item.username} · {item.is_active ? 'Active' : 'Inactive'}{item.is_staff ? ' · Admin' : ''}
                          </Text>
                        </Box>
                      </Group>
                    </UnstyledButton>
                  ))}
                </Stack>
              </Box>
            )}

            <Stack>
              <Text fw={700}>{selectedUser ? (canManageUsers ? 'Edit user' : 'Edit account') : 'Create user'}</Text>
              <TextInput
                label="Username"
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
                required
              />
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <TextInput
                  label="First name"
                  value={firstName}
                  onChange={(event) => setFirstName(event.currentTarget.value)}
                />
                <TextInput
                  label="Last name"
                  value={lastName}
                  onChange={(event) => setLastName(event.currentTarget.value)}
                />
              </SimpleGrid>
              <PasswordInput
                label={selectedUser ? 'New password' : 'Password'}
                description={selectedUser ? 'Leave blank to keep current password.' : undefined}
                value={password}
                onChange={(event) => setPassword(event.currentTarget.value)}
                required={!selectedUser}
              />
              <PasswordInput
                label="Confirm password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.currentTarget.value)}
                required={!selectedUser || Boolean(password)}
              />
              {canManageUsers && (
                <>
                  <Switch
                    label="Active user"
                    checked={isActive}
                    onChange={(event) => setIsActive(event.currentTarget.checked)}
                  />
                  <Switch
                    label="Admin/staff user"
                    checked={isStaff}
                    onChange={(event) => setIsStaff(event.currentTarget.checked)}
                  />
                  <Divider label="Permissions" labelPosition="left" />
                  <Switch
                    label="Edit devices"
                    description="Update device details and delete devices."
                    checked={isStaff || canEditDevices}
                    disabled={isStaff}
                    onChange={(event) => setCanEditDevices(event.currentTarget.checked)}
                  />
                  <Switch
                    label="Edit Home Map"
                    description="Rearrange rooms and reset the saved layout."
                    checked={isStaff || canEditHomeMap}
                    disabled={isStaff}
                    onChange={(event) => setCanEditHomeMap(event.currentTarget.checked)}
                  />
                  <Switch
                    label="Run scans"
                    description="Start manual network scans."
                    checked={isStaff || canRunScans}
                    disabled={isStaff}
                    onChange={(event) => setCanRunScans(event.currentTarget.checked)}
                  />
                  {isStaff && (
                    <Text size="xs" c="dimmed">
                      Admin users always have all permissions.
                    </Text>
                  )}
                </>
              )}
            </Stack>
          </SimpleGrid>

          <Divider />
          <Group justify="space-between">
            {canManageUsers ? (
              <Stack gap={4}>
                <Button
                  color="red"
                  variant="light"
                  leftSection={<IconUserMinus size={18} />}
                  disabled={!selectedUser || selectedUserIsLastAdmin}
                  onClick={() => setDeleteTarget(selectedUser)}
                >
                  Delete
                </Button>
                {selectedUserIsLastAdmin && (
                  <Text size="xs" c="dimmed">
                    The only admin user cannot be deleted.
                  </Text>
                )}
              </Stack>
            ) : <Box />}
            <Group>
              <Button variant="default" onClick={closeModal}>
                Close
              </Button>
              <Button onClick={saveUser} loading={saving} disabled={!selectedUser && !canManageUsers}>
                Save
              </Button>
            </Group>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Delete user"
        centered
      >
        <Stack>
          <Text>Are you sure you want to delete this user?</Text>
          <Text size="sm" c="dimmed">
            {deleteTarget?.username} will no longer be able to sign in.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              color="red"
              leftSection={<IconUserMinus size={18} />}
              onClick={deleteUser}
              loading={saving}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
