import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

class MemoryStorage {
  #values = new Map();

  clearCalls = 0;

  get length() {
    return this.#values.size;
  }

  clear() {
    this.clearCalls += 1;
    this.#values.clear();
  }

  getItem(key) {
    return this.#values.has(key) ? this.#values.get(key) : null;
  }

  key(index) {
    return [...this.#values.keys()][index] ?? null;
  }

  removeItem(key) {
    this.#values.delete(key);
  }

  reset() {
    this.#values.clear();
    this.clearCalls = 0;
  }

  setItem(key, value) {
    this.#values.set(key, String(value));
  }
}

globalThis.localStorage = new MemoryStorage();
globalThis.sessionStorage = new MemoryStorage();
globalThis.window = { location: { search: '?sid=wechat-pilot' } };
globalThis.fetch = async () => ({ ok: true });

const { get, set } = await import('../src/surfgymBridge.js');

const canonicalState = {
  user: { userId: 'user_1', nickname: 'Alice' },
  contacts: [],
  conversations: [],
  messages: {},
  moments: [],
  groups: [],
  favorites: [],
  initialState: { moments: [] },
};

beforeEach(() => {
  localStorage.reset();
  sessionStorage.reset();
  window.location.search = '?sid=wechat-pilot';
});

test('installs the shared SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('writes through the canonical whitelist-preserving persistence path', async () => {
  localStorage.setItem(
    'wechat_mock_data_wechat-pilot',
    JSON.stringify({ ...canonicalState, _sid: 'private', initialize: 'private' }),
  );

  const moments = [{ postId: 'moment-new', content: 'hello' }];
  await set({ target: 'app_state', path: 'moments' }, moments);

  assert.deepEqual(await get({ target: 'app_state', path: ['moments'] }), moments);
  const persisted = JSON.parse(
    localStorage.getItem('wechat_mock_data_wechat-pilot'),
  );
  assert.deepEqual(Object.keys(persisted).sort(), Object.keys(canonicalState).sort());
  assert.equal(persisted._sid, undefined);
  assert.equal(persisted.initialize, undefined);
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'wechat_mock_data_wechat-pilot',
    JSON.stringify({ ...canonicalState, moments: [{ postId: 'moment_1' }] }),
  );

  assert.equal(
    await get({ script: "state.moments.some(item => item.postId === 'moment_1')" }),
    true,
  );
});

test('release removes only the current SID keys without broad ErrorBoundary cleanup', async () => {
  localStorage.setItem('wechat_mock_data_wechat-pilot', '{}');
  localStorage.setItem('wechat_mock_data_initialState_wechat-pilot', '{}');
  localStorage.setItem('wechat_chat_bg_wechat-pilot_contact-1', 'green');
  localStorage.setItem('wechat_chat_bg_wechat-pilot_contact-2', 'blue');

  localStorage.setItem('wechat_mock_data_other-task', '{"keep":true}');
  localStorage.setItem(
    'wechat_mock_data_initialState_other-task',
    '{"keep":true}',
  );
  localStorage.setItem('wechat_chat_bg_other-task_contact-1', 'red');
  localStorage.setItem('unrelated_key', 'keep');
  sessionStorage.setItem('mock_sid', 'wechat-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);

  assert.equal(localStorage.getItem('wechat_mock_data_wechat-pilot'), null);
  assert.equal(
    localStorage.getItem('wechat_mock_data_initialState_wechat-pilot'),
    null,
  );
  assert.equal(
    localStorage.getItem('wechat_chat_bg_wechat-pilot_contact-1'),
    null,
  );
  assert.equal(
    localStorage.getItem('wechat_chat_bg_wechat-pilot_contact-2'),
    null,
  );
  assert.equal(
    localStorage.getItem('wechat_mock_data_other-task'),
    '{"keep":true}',
  );
  assert.equal(
    localStorage.getItem('wechat_mock_data_initialState_other-task'),
    '{"keep":true}',
  );
  assert.equal(
    localStorage.getItem('wechat_chat_bg_other-task_contact-1'),
    'red',
  );
  assert.equal(localStorage.getItem('unrelated_key'), 'keep');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
  assert.equal(localStorage.clearCalls, 0);
});

test('rejects missing SID and unsupported state specs', async () => {
  window.location.search = '';
  await assert.rejects(
    () => get({ target: 'app_state', path: 'moments' }),
    /session ID is unavailable/,
  );

  window.location.search = '?sid=wechat-pilot';
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
