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

const fetchCalls = [];
globalThis.localStorage = new MemoryStorage();
globalThis.sessionStorage = new MemoryStorage();
globalThis.window = { location: { search: '?sid=shopify-pilot' } };
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  return { ok: true, json: async () => ({}) };
};

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  fetchCalls.length = 0;
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=shopify-pilot';
});

test('installs the SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('writes through canonical saveState without replacing siblings', async () => {
  localStorage.setItem(
    'shopify_mock_state_shopify-pilot',
    JSON.stringify({ products: [{ id: 'product-1', status: 'draft' }], orders: [] }),
  );

  await set({ target: 'app_state', path: 'products.0.status' }, 'active');

  assert.equal(
    await get({ target: 'app_state', path: ['products', '0', 'status'] }),
    'active',
  );
  assert.equal(
    Array.isArray(await get({ target: 'app_state', path: 'products' })),
    true,
  );
  assert.deepEqual(await get({ target: 'app_state', path: 'orders' }), []);
  assert.equal(fetchCalls.at(-1).url, '/post?sid=shopify-pilot');
  assert.equal(
    JSON.parse(fetchCalls.at(-1).options.body).action,
    'set_current',
  );
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'shopify_mock_state_shopify-pilot',
    JSON.stringify({ products: [{ id: 'product-1', status: 'active' }] }),
  );

  assert.equal(
    await get({ script: "state.products.some(product => product.status === 'active')" }),
    true,
  );
});

test('release removes only the current SID state and initial snapshot', async () => {
  localStorage.setItem('shopify_mock_state_shopify-pilot', '{}');
  localStorage.setItem('shopify_mock_initialState_shopify-pilot', '{}');
  localStorage.setItem('shopify_mock_state_other-task', '{}');
  sessionStorage.setItem('mock_sid', 'shopify-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('shopify_mock_state_shopify-pilot'), null);
  assert.equal(
    localStorage.getItem('shopify_mock_initialState_shopify-pilot'),
    null,
  );
  assert.equal(localStorage.getItem('shopify_mock_state_other-task'), '{}');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
  assert.equal(fetchCalls.length, 0);
});

test('release rejects a missing SID and preserves unscoped state', async () => {
  window.location.search = '';
  sessionStorage.clear();
  localStorage.setItem('shopify_mock_state', 'base-current');
  localStorage.setItem('shopify_mock_initialState', 'base-initial');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /non-empty session ID/,
  );
  assert.equal(localStorage.getItem('shopify_mock_state'), 'base-current');
  assert.equal(localStorage.getItem('shopify_mock_initialState'), 'base-initial');
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
