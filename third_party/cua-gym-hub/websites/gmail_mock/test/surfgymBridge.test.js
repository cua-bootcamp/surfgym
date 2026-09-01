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
globalThis.window = { location: { search: '?sid=gmail-pilot' } };

let fetchedUrls = [];
globalThis.fetch = async url => {
  fetchedUrls.push(url);
  return {
    ok: true,
    json: async () => ({ has_custom_state: true, stored_state: { emails: [] } }),
  };
};

const { get, set } = await import('../src/surfgymBridge.js');
const { fetchCustomState } = await import('../src/data/mockData.js');

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  fetchedUrls = [];
  window.location.search = '?sid=gmail-pilot';
});

test('installs the shared SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('reads and writes SID-scoped app state paths without replacing siblings', async () => {
  localStorage.setItem(
    'xmail-clone-state_gmail-pilot',
    JSON.stringify({ drafts: [], currentUserId: 'user_admin' }),
  );

  await set({ target: 'app_state', path: 'drafts' }, [{ id: 'draft_12' }]);

  assert.deepEqual(
    await get({ target: 'app_state', path: ['drafts'] }),
    [{ id: 'draft_12' }],
  );
  assert.equal(
    await get({ target: 'app_state', path: 'currentUserId' }),
    'user_admin',
  );
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'xmail-clone-state_gmail-pilot',
    JSON.stringify({ drafts: [{ id: 'draft_12' }] }),
  );

  assert.equal(
    await get({ script: "state.drafts.some((draft) => draft.id === 'draft_12')" }),
    true,
  );
});

test('requests the custom initial state for the active SID', async () => {
  assert.deepEqual(await fetchCustomState('gmail-pilot'), { emails: [] });
  assert.deepEqual(fetchedUrls, ['/state?sid=gmail-pilot']);
});

test('release removes only the current SID state and its initial snapshot', async () => {
  localStorage.setItem('xmail-clone-state_gmail-pilot', '{}');
  localStorage.setItem('xmail-clone-initialState_gmail-pilot', '{}');
  localStorage.setItem('xmail-clone-state_other-task', '{}');
  sessionStorage.setItem('mock_sid', 'gmail-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('xmail-clone-state_gmail-pilot'), null);
  assert.equal(
    localStorage.getItem('xmail-clone-initialState_gmail-pilot'),
    null,
  );
  assert.equal(localStorage.getItem('xmail-clone-state_other-task'), '{}');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
});

test('release rejects a missing SID and preserves unscoped state', async () => {
  window.location.search = '';
  localStorage.setItem('xmail-clone-state', '{}');
  localStorage.setItem('xmail-clone-initialState', '{}');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /non-empty SID/,
  );
  assert.equal(localStorage.getItem('xmail-clone-state'), '{}');
  assert.equal(localStorage.getItem('xmail-clone-initialState'), '{}');
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
