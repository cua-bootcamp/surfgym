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
globalThis.window = { location: { search: '?sid=pilot-task' } };
globalThis.fetch = async () => ({ ok: true });

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=pilot-task';
});

test('installs the shared SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('reads and writes SID-scoped app state paths without replacing siblings', async () => {
  localStorage.setItem(
    'instacart_mock_state_pilot-task',
    JSON.stringify({ cart: [], deliveryAddressId: 'addr_1' }),
  );

  await set({ target: 'app_state', path: 'cart' }, [{ productId: 'prod_77' }]);

  assert.deepEqual(await get({ target: 'app_state', path: ['cart'] }), [
    { productId: 'prod_77' },
  ]);
  assert.equal(
    await get({ target: 'app_state', path: 'deliveryAddressId' }),
    'addr_1',
  );
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'instacart_mock_state_pilot-task',
    JSON.stringify({ cart: [{ productId: 'prod_77' }, { productId: 'prod_80' }] }),
  );

  assert.equal(
    await get({
      script:
        "state.cart.some((item) => item.productId === 'prod_77')",
    }),
    true,
  );
});

test('release removes only the current SID state and its initial snapshot', async () => {
  localStorage.setItem('instacart_mock_state_pilot-task', '{}');
  localStorage.setItem('instacart_mock_initialState_pilot-task', '{}');
  localStorage.setItem('instacart_mock_state_other-task', '{}');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('instacart_mock_state_pilot-task'), null);
  assert.equal(localStorage.getItem('instacart_mock_initialState_pilot-task'), null);
  assert.equal(localStorage.getItem('instacart_mock_state_other-task'), '{}');
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
