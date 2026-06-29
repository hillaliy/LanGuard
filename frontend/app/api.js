const CONFIGURED_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

function getApiBase() {
  if (CONFIGURED_API_BASE) {
    return CONFIGURED_API_BASE;
  }

  if (typeof window !== 'undefined' && window.location.port === '3000') {
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

function apiConnectionMessage(url) {
  return `Backend server is not reachable at ${url.origin}. Check that Django is running, then refresh.`;
}

export async function apiRequest(path, options = {}) {
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
    });
  } catch (error) {
    throw new Error(apiConnectionMessage(url));
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('text/html') || text.trim().startsWith('<')) {
        throw new Error(
          response.ok
            ? `Backend returned an HTML page instead of API data from ${url.pathname}.`
            : `Backend returned an HTML error page for ${url.pathname}. Check the Django server logs.`
        );
      }
      throw new Error(`Backend returned an unreadable API response from ${url.pathname}.`);
    }
  }

  if (!response.ok) {
    const message =
      payload?.detail ||
      payload?.error ||
      payload?.info ||
      'Request failed';
    throw new Error(message);
  }

  return payload;
}
