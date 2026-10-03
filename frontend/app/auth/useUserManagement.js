import { useEffect, useState } from 'react';
import { apiRequest, clearStoredUser } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';
import { capitalizeName } from './user';

export default function useUserManagement({ opened, currentUser, onCurrentUserUpdated }) {
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

  return {
    users, selectedUserId, setSelectedUserId, selectedUser, canManageUsers, selectedUserIsLastAdmin,
    username, setUsername, firstName, setFirstName, lastName, setLastName,
    password, setPassword, passwordConfirm, setPasswordConfirm,
    isActive, setIsActive, isStaff, setIsStaff,
    canEditDevices, setCanEditDevices, canEditHomeMap, setCanEditHomeMap, canRunScans, setCanRunScans,
    loading, saving, error, deleteTarget, setDeleteTarget, saveUser, deleteUser,
  };
}
