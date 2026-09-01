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
globalThis.window = { location: { search: '?sid=instagram-pilot' } };
globalThis.fetch = async () => ({ ok: true });

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=instagram-pilot';
});

test('installs the shared SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('reads and writes SID-scoped app state paths without replacing siblings', async () => {
  localStorage.setItem(
    'instagram_mock_state_instagram-pilot',
    JSON.stringify({ savedPostIds: [], currentUserId: 'user_admin' }),
  );

  await set({ target: 'app_state', path: 'savedPostIds' }, ['post_12']);

  assert.deepEqual(
    await get({ target: 'app_state', path: ['savedPostIds'] }),
    ['post_12'],
  );
  assert.equal(
    await get({ target: 'app_state', path: 'currentUserId' }),
    'user_admin',
  );
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'instagram_mock_state_instagram-pilot',
    JSON.stringify({ savedPostIds: ['post_12'] }),
  );

  assert.equal(
    await get({ script: "state.savedPostIds.includes('post_12')" }),
    true,
  );
});

test('release removes only the current SID state and its initial snapshot', async () => {
  localStorage.setItem('instagram_mock_state_instagram-pilot', '{}');
  localStorage.setItem('instagram_mock_initialState_instagram-pilot', '{}');
  localStorage.setItem('instagram_mock_state_other-task', '{}');
  sessionStorage.setItem('mock_sid', 'instagram-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('instagram_mock_state_instagram-pilot'), null);
  assert.equal(
    localStorage.getItem('instagram_mock_initialState_instagram-pilot'),
    null,
  );
  assert.equal(localStorage.getItem('instagram_mock_state_other-task'), '{}');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
});

test('release rejects a missing SID and preserves unscoped state', async () => {
  window.location.search = '';
  localStorage.setItem('instagram_mock_state', '{}');
  localStorage.setItem('instagram_mock_initialState', '{}');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /non-empty SID/,
  );
  assert.equal(localStorage.getItem('instagram_mock_state'), '{}');
  assert.equal(localStorage.getItem('instagram_mock_initialState'), '{}');
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
