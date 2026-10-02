import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconShieldCheck } from '@tabler/icons-react';
import { BACKEND_UNAVAILABLE_MESSAGE } from '../api';

export function showServerNotification(payload, color = 'teal') {
  const serverNotification = payload?.notification;
  if (!serverNotification?.title || !serverNotification?.message) {
    return false;
  }

  notifications.show({
    title: serverNotification.title,
    message: serverNotification.message,
    color,
    icon: color === 'red' ? <IconAlertCircle size={18} /> : <IconShieldCheck size={18} />,
  });
  return true;
}

export function showErrorNotification(titleOrError, message) {
  if (titleOrError instanceof Error) {
    if (showServerNotification({ notification: titleOrError.notification }, 'red')) {
      return;
    }
    message = titleOrError.message;
    titleOrError = 'Request failed';
  }

  const backendUnavailable = message === BACKEND_UNAVAILABLE_MESSAGE;
  notifications.show({
    title: backendUnavailable ? 'Server unavailable' : titleOrError,
    message,
    color: 'red',
    icon: <IconAlertCircle size={18} />,
  });
}
