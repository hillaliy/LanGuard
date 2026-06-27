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
  const username = window.localStorage.getItem('username');
  return token && username ? { token, username } : null;
}

export function storeUser(user) {
  window.localStorage.setItem('token', user.token);
  window.localStorage.setItem('username', user.username);
}

export function clearStoredUser() {
  window.localStorage.removeItem('token');
  window.localStorage.removeItem('username');
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

export async function apiRequest(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  const token = getToken();

  if (token) {
    headers.Authorization = `Token ${token}`;
  }

  const response = await fetch(buildUrl(path, options.params), {
    method: options.method || 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new Error(
        `Expected JSON from ${response.url}, but received a non-JSON response.`
      );
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
