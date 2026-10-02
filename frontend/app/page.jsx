'use client';

import { useEffect, useState } from 'react';
import { getStoredUser } from './api';
import { AuthScreen } from './auth/AuthViews';
import AppShell from './shell/AppShell';

export function LanGuardApplication({
  initialDeviceId = null,
  initialView = 'dashboard',
}) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(getStoredUser());
    setReady(true);
  }, []);

  if (!ready) {
    return null;
  }

  if (!user) {
    return <AuthScreen onLogin={setUser} />;
  }

  return (
    <AppShell
      user={user}
      onLogout={() => setUser(null)}
      onUserUpdated={setUser}
      initialDeviceId={initialDeviceId}
      initialView={initialView}
    />
  );
}

export default function Home() {
  return <LanGuardApplication initialView="dashboard" />;
}
