import { useEffect, useState } from 'react';
import { useDisclosure } from '@mantine/hooks';
import { apiRequest, clearStoredUser, storeUser } from '../api';
import { showErrorNotification } from '../utils/notifications';
import { useVersionStatus } from './useVersionStatus';

function capabilitiesFromUser(user) {
  return {
    can_edit_devices: Boolean(user?.is_staff || user?.is_superuser || user?.can_edit_devices),
    can_edit_home_map: Boolean(user?.is_staff || user?.is_superuser || user?.can_edit_home_map),
    can_run_scans: Boolean(user?.is_staff || user?.is_superuser || user?.can_run_scans),
  };
}

export function useLanGuardSession({ user, onLogout, onUserUpdated }) {
  const [accessCapabilities, setAccessCapabilities] = useState(() => capabilitiesFromUser(user));
  const [logoutModalOpened, logoutModal] = useDisclosure(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [usersModalOpened, usersModal] = useDisclosure(false);
  const [scanDetailsOpened, scanDetailsModal] = useDisclosure(false);
  const [mobileNavigationOpened, mobileNavigation] = useDisclosure(false);
  const versionStatus = useVersionStatus();
  const canManageUsers = Boolean(user?.is_staff || user?.is_superuser);

  useEffect(() => {
    setAccessCapabilities(capabilitiesFromUser(user));
  }, [
    user?.is_staff,
    user?.is_superuser,
    user?.can_edit_devices,
    user?.can_edit_home_map,
    user?.can_run_scans,
  ]);

  async function logout() {
    setLoggingOut(true);
    try {
      await apiRequest('logout/', { method: 'POST' });
      clearStoredUser();
      onLogout();
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setLoggingOut(false);
    }
  }

  function updateCurrentUser(nextUser) {
    if (!nextUser) {
      onLogout();
      return;
    }
    storeUser(nextUser);
    onUserUpdated(nextUser);
  }

  return {
    accessCapabilities,
    setAccessCapabilities,
    canManageUsers,
    canEditDevices: canManageUsers || Boolean(accessCapabilities.can_edit_devices),
    canEditHomeMap: canManageUsers || Boolean(accessCapabilities.can_edit_home_map),
    canRunScans: canManageUsers || Boolean(accessCapabilities.can_run_scans),
    logoutModalOpened,
    logoutModal,
    loggingOut,
    usersModalOpened,
    usersModal,
    scanDetailsOpened,
    scanDetailsModal,
    mobileNavigationOpened,
    mobileNavigation,
    logout,
    updateCurrentUser,
    ...versionStatus,
  };
}
