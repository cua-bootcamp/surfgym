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
globalThis.window = { location: { search: '?sid=jira-pilot' } };
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  return { ok: true, json: async () => ({}) };
};

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  fetchCalls.length = 0;
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=jira-pilot';
});

test('installs the SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('writes through canonical saveState and preserves arrays and siblings', async () => {
  localStorage.setItem(
    'jira_clone_state_jira-pilot',
    JSON.stringify({ issues: [{ id: 'i1', status: 'To Do' }], users: [] }),
  );

  await set({ target: 'app_state', path: 'issues.0.status' }, 'Done');

  assert.equal(
    await get({ target: 'app_state', path: ['issues', '0', 'status'] }),
    'Done',
  );
  assert.equal(Array.isArray(await get({ target: 'app_state', path: 'issues' })), true);
  assert.deepEqual(await get({ target: 'app_state', path: 'users' }), []);
  assert.equal(fetchCalls.at(-1).url, '/post?sid=jira-pilot');
  assert.equal(JSON.parse(fetchCalls.at(-1).options.body).action, 'set_current');
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'jira_clone_state_jira-pilot',
    JSON.stringify({ issues: [{ id: 'i1', status: 'Done' }] }),
  );

  assert.equal(
    await get({ script: "state.issues.some(issue => issue.status === 'Done')" }),
    true,
  );
});

test('release removes only the current SID state and initial snapshot', async () => {
  localStorage.setItem('jira_clone_state_jira-pilot', '{}');
  localStorage.setItem('jira_clone_initialState_jira-pilot', '{}');
  localStorage.setItem('jira_clone_state_other-task', '{}');
  sessionStorage.setItem('mock_sid', 'jira-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('jira_clone_state_jira-pilot'), null);
  assert.equal(localStorage.getItem('jira_clone_initialState_jira-pilot'), null);
  assert.equal(localStorage.getItem('jira_clone_state_other-task'), '{}');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
  assert.equal(fetchCalls.length, 0);
});

test('release without a SID rejects and preserves unscoped base state', async () => {
  window.location.search = '';
  localStorage.setItem('jira_clone_state', '{"current":true}');
  localStorage.setItem('jira_clone_initialState', '{"initial":true}');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /requires a non-empty SID/,
  );
  assert.equal(localStorage.getItem('jira_clone_state'), '{"current":true}');
  assert.equal(
    localStorage.getItem('jira_clone_initialState'),
    '{"initial":true}',
  );
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
