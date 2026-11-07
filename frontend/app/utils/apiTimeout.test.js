import assert from 'node:assert/strict';
import test from 'node:test';
import { apiRequest } from '../api.js';

function setup(t) {
  t.mock.method(globalThis, 'fetch');
  const previous = globalThis.window;
  globalThis.window = { location: { origin: 'http://localhost' }, localStorage: { getItem: () => 'test-token' } };
  t.after(() => { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; });
}

function rejectOnAbort(signal) {
  return new Promise((_, reject) => signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }));
}

test('opt-in deadline aborts a fetch that never responds', async (t) => {
  setup(t);
  fetch.mock.mockImplementation((_, options) => rejectOnAbort(options.signal));
  await assert.rejects(apiRequest('network-map/preferences/', { timeoutMs: 10 }), { code: 'request_timeout' });
});

test('deadline also covers a response body that never finishes', async (t) => {
  setup(t);
  fetch.mock.mockImplementation(async (_, options) => ({ ok: true, text: () => rejectOnAbort(options.signal) }));
  await assert.rejects(apiRequest('network-map/preferences/', { timeoutMs: 10 }), { code: 'request_timeout' });
});

test('successful requests clear their abort timer', async (t) => {
  setup(t);
  let signal;
  fetch.mock.mockImplementation(async (_, options) => {
    signal = options.signal;
    return { ok: true, text: async () => JSON.stringify({ data: { show_lldp_suggestions: true } }) };
  });
  assert.deepEqual(await apiRequest('network-map/preferences/', { timeoutMs: 10 }), { data: { show_lldp_suggestions: true } });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(signal.aborted, false);
});

test('unrelated callers retain existing request behavior without a deadline', async (t) => {
  setup(t);
  fetch.mock.mockImplementation(async (_, options) => {
    assert.equal(options.signal, undefined);
    assert.equal(options.headers.Authorization, 'Token test-token');
    return { ok: false, status: 400, text: async () => JSON.stringify({ detail: 'Invalid preference' }) };
  });
  await assert.rejects(apiRequest('network-map/preferences/'), { message: 'Invalid preference' });
});
