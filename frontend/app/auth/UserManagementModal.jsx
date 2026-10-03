import { Alert, Button, Group, LoadingOverlay, Modal, Stack, Text } from '@mantine/core';
import { IconAlertCircle, IconUserMinus } from '@tabler/icons-react';
import UserManagementForm from './UserManagementForm';
import useUserManagement from './useUserManagement';

export default function UserManagementModal({ opened, onClose, currentUser, onCurrentUserUpdated }) {
  const management = useUserManagement({ opened, currentUser, onCurrentUserUpdated });
  const { canManageUsers, loading, saving, error, deleteTarget, setDeleteTarget, deleteUser } = management;

  function closeModal() {
    setDeleteTarget(null);
    onClose();
  }

  return (
    <>
      <Modal opened={opened} onClose={closeModal} title={canManageUsers ? 'Users' : 'My account'} centered size="lg">
        <LoadingOverlay visible={loading} />
        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />} mb="md">
            {error}
          </Alert>
        )}
        <UserManagementForm management={management} onClose={closeModal} />
      </Modal>

      <Modal
        opened={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Delete user"
        centered
      >
        <Stack>
          <Text>Are you sure you want to delete this user?</Text>
          <Text size="sm" c="dimmed">{deleteTarget?.username} will no longer be able to sign in.</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>Cancel</Button>
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
