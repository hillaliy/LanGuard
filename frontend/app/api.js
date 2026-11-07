const CONFIGURED_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;
export const BACKEND_UNAVAILABLE_MESSAGE =
  'LanGuard cannot reach the server right now. Wait a moment, then try again.';

function apiError(message, notification = null) {
  const safeMessage =
    typeof message === 'string' && message.trim()
      ? message
      : notification?.message || 'The request could not be completed.';
  const error = new Error(safeMessage);
  error.notification = notification || {
    title:
      safeMessage === BACKEND_UNAVAILABLE_MESSAGE
        ? 'Server unavailable'
        : 'Request failed',
    message: safeMessage,
  };
  return error;
}

function responseError(response, message, notification) {
  const error = apiError(message, notification);
  error.status = response.status;
  return error;
}

function getApiBase() {
  if (CONFIGURED_API_BASE) {
    return CONFIGURED_API_BASE;
  }

  if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000/api/v1';
  }

  return '/api/v1';
}

export function getAdminUrl() {
  if (typeof window === 'undefined') {
    return '/admin/';
  }

  const apiBase = getApiBase();
  const adminUrl = new URL(apiBase, window.location.origin);
  adminUrl.pathname = '/admin/';
  adminUrl.search = '';
  adminUrl.hash = '';
  return adminUrl.toString();
}

function getToken() {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem('token');
}

export function getStoredUser() {
  if (typeof window === 'undefined') {
    return null;
  }

  const token = window.localStorage.getItem('token');
  const id = window.localStorage.getItem('user_id');
  const username = window.localStorage.getItem('username');
  const firstName = window.localStorage.getItem('first_name') || '';
  const lastName = window.localStorage.getItem('last_name') || '';
  const isStaff = window.localStorage.getItem('is_staff') === 'true';
  const isSuperuser = window.localStorage.getItem('is_superuser') === 'true';
  return token && username
    ? {
        token,
        id: id ? Number(id) : null,
        username,
        first_name: firstName,
        last_name: lastName,
        is_staff: isStaff,
        is_superuser: isSuperuser,
      }
    : null;
}

export function storeUser(user) {
  window.localStorage.setItem('token', user.token);
  window.localStorage.setItem('user_id', String(user.id || ''));
  window.localStorage.setItem('username', user.username);
  window.localStorage.setItem('first_name', user.first_name || '');
  window.localStorage.setItem('last_name', user.last_name || '');
  window.localStorage.setItem('is_staff', String(Boolean(user.is_staff)));
  window.localStorage.setItem('is_superuser', String(Boolean(user.is_superuser)));
}

export function clearStoredUser() {
  window.localStorage.removeItem('token');
  window.localStorage.removeItem('user_id');
  window.localStorage.removeItem('username');
  window.localStorage.removeItem('first_name');
  window.localStorage.removeItem('last_name');
  window.localStorage.removeItem('is_staff');
  window.localStorage.removeItem('is_superuser');
}

function buildUrl(path, params = {}) {
  const normalizedBase = getApiBase().replace(/\/$/, '');
  const normalizedPath = path.replace(/^\//, '');
  const url = new URL(`${normalizedBase}/${normalizedPath}`, window.location.origin);

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value);
    }
  });

  return url;
}

async function performApiRequest(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  const token = getToken();

  if (token) {
    headers.Authorization = `Token ${token}`;
  }

  const url = buildUrl(path, options.params);
  let response;

  try {
    response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: 'no-store',
      signal: options.signal,
    });
  } catch (error) {
    throw apiError(BACKEND_UNAVAILABLE_MESSAGE);
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('text/html') || text.trim().startsWith('<')) {
        if (!response.ok) {
          throw responseError(response, BACKEND_UNAVAILABLE_MESSAGE);
        }
        throw responseError(response, BACKEND_UNAVAILABLE_MESSAGE);
      }
      if (response.status >= 500) {
        throw responseError(response, BACKEND_UNAVAILABLE_MESSAGE);
      }
      throw responseError(response, BACKEND_UNAVAILABLE_MESSAGE);
    }
  }

  if (!response.ok) {
    const message =
      payload?.detail ||
      payload?.error ||
      payload?.info ||
      payload?.notification?.message;
    if (message) {
      throw responseError(response, message, payload?.notification);
    }
    if (response.status >= 500) {
      throw responseError(response, BACKEND_UNAVAILABLE_MESSAGE);
    }
    throw responseError(response, 'The request could not be completed.', payload?.notification);
  }

  return payload;
}

export async function apiRequest(path, options = {}) {
  if (!options.timeoutMs) return performApiRequest(path, options);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs);
  try {
    return await performApiRequest(path, { ...options, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) {
      const timeoutError = apiError('The server did not confirm the request in time. Refresh before trying again.');
      timeoutError.code = 'request_timeout';
      throw timeoutError;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
