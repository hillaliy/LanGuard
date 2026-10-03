import {
  Box, Button, Divider, Group, PasswordInput, SimpleGrid, Stack, Switch, Text, TextInput, UnstyledButton,
} from '@mantine/core';
import { IconUserEdit, IconUserMinus, IconUserPlus } from '@tabler/icons-react';
import { userDisplayName } from './user';

export default function UserManagementForm({ management, onClose }) {
  const {
    users, selectedUserId, setSelectedUserId, selectedUser, canManageUsers, selectedUserIsLastAdmin,
    username, setUsername, firstName, setFirstName, lastName, setLastName,
    password, setPassword, passwordConfirm, setPasswordConfirm,
    isActive, setIsActive, isStaff, setIsStaff,
    canEditDevices, setCanEditDevices, canEditHomeMap, setCanEditHomeMap, canRunScans, setCanRunScans,
    saving, setDeleteTarget, saveUser,
  } = management;

  return (
    <Stack>
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
              {isStaff && <Text size="xs" c="dimmed">Admin users always have all permissions.</Text>}
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
              <Text size="xs" c="dimmed">The only admin user cannot be deleted.</Text>
            )}
          </Stack>
        ) : <Box />}
        <Group>
          <Button variant="default" onClick={onClose}>Close</Button>
          <Button onClick={saveUser} loading={saving} disabled={!selectedUser && !canManageUsers}>Save</Button>
        </Group>
      </Group>
    </Stack>
  );
}
