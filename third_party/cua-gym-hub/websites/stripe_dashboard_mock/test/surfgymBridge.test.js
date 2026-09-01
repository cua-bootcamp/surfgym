import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

class MemoryStorage {
  #values = new Map();

  clear() {
    this.#values.clear();
  }

  getItem(key) {
    return this.#values.has(key) ? this.#values.get(key) : null;
  }

  removeItem(key) {
    this.#values.delete(key);
  }

  setItem(key, value) {
    this.#values.set(key, String(value));
  }
}

globalThis.localStorage = new MemoryStorage();
globalThis.sessionStorage = new MemoryStorage();
globalThis.window = { location: { search: '?sid=stripe-pilot' } };
globalThis.fetch = async () => ({ ok: true });

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=stripe-pilot';
});

test('installs the shared SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('reads and writes SID-scoped app state paths without replacing siblings', async () => {
  localStorage.setItem(
    'stripe_dashboard_state_stripe-pilot',
    JSON.stringify({ customers: [], currentUserId: 'user_admin' }),
  );

  await set({ target: 'app_state', path: 'customers' }, [{ id: 'cus_12' }]);

  assert.deepEqual(
    await get({ target: 'app_state', path: ['customers'] }),
    [{ id: 'cus_12' }],
  );
  assert.equal(
    await get({ target: 'app_state', path: 'currentUserId' }),
    'user_admin',
  );
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'stripe_dashboard_state_stripe-pilot',
    JSON.stringify({ customers: [{ id: 'cus_12' }] }),
  );

  assert.equal(
    await get({ script: "state.customers.some((customer) => customer.id === 'cus_12')" }),
    true,
  );
});

test('release removes only the current SID state, initial snapshot, and seeded marker', async () => {
  localStorage.setItem('stripe_dashboard_state_stripe-pilot', '{}');
  localStorage.setItem('stripe_dashboard_initialState_stripe-pilot', '{}');
  localStorage.setItem('stripe_dashboard_initialState_serverSeeded_stripe-pilot', 'true');
  localStorage.setItem('stripe_dashboard_state_other-task', '{}');
  localStorage.setItem('stripe_dashboard_initialState_serverSeeded_other-task', 'true');
  sessionStorage.setItem('stripe_mock_sid', 'stripe-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('stripe_dashboard_state_stripe-pilot'), null);
  assert.equal(
    localStorage.getItem('stripe_dashboard_initialState_stripe-pilot'),
    null,
  );
  assert.equal(
    localStorage.getItem('stripe_dashboard_initialState_serverSeeded_stripe-pilot'),
    null,
  );
  assert.equal(localStorage.getItem('stripe_dashboard_state_other-task'), '{}');
  assert.equal(
    localStorage.getItem('stripe_dashboard_initialState_serverSeeded_other-task'),
    'true',
  );
  assert.equal(sessionStorage.getItem('stripe_mock_sid'), null);
});

test('release rejects a missing SID and preserves unscoped state', async () => {
  window.location.search = '';
  localStorage.setItem('stripe_dashboard_state', '{}');
  localStorage.setItem('stripe_dashboard_initialState', '{}');
  localStorage.setItem('stripe_dashboard_initialState_serverSeeded', 'true');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /non-empty SID/,
  );
  assert.equal(localStorage.getItem('stripe_dashboard_state'), '{}');
  assert.equal(localStorage.getItem('stripe_dashboard_initialState'), '{}');
  assert.equal(
    localStorage.getItem('stripe_dashboard_initialState_serverSeeded'),
    'true',
  );
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
