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
globalThis.window = { location: { search: '?sid=teams-pilot' } };
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  return { ok: true, json: async () => ({}) };
};

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  fetchCalls.length = 0;
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=teams-pilot';
});

test('installs the SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('writes through canonical saveState and preserves arrays and siblings', async () => {
  localStorage.setItem(
    'teamsState_teams-pilot',
    JSON.stringify({ teams: [{ teamId: 'team_1', isFavorite: false }], chats: [] }),
  );

  await set({ target: 'app_state', path: 'teams.0.isFavorite' }, true);
  await new Promise(resolve => setTimeout(resolve, 350));

  assert.equal(
    await get({ target: 'app_state', path: ['teams', '0', 'isFavorite'] }),
    true,
  );
  assert.equal(Array.isArray(await get({ target: 'app_state', path: 'teams' })), true);
  assert.deepEqual(await get({ target: 'app_state', path: 'chats' }), []);
  assert.equal(fetchCalls.at(-1).url, '/post?sid=teams-pilot');
  assert.equal(JSON.parse(fetchCalls.at(-1).options.body).action, 'set_current');
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'teamsState_teams-pilot',
    JSON.stringify({ teams: [{ teamId: 'team_1', isFavorite: true }] }),
  );

  assert.equal(
    await get({ script: 'state.teams.some(team => team.isFavorite)' }),
    true,
  );
});

test('release removes only the current SID state and initial snapshot', async () => {
  localStorage.setItem('teamsState_teams-pilot', '{}');
  localStorage.setItem('teamsInitialState_teams-pilot', '{}');
  localStorage.setItem('teamsState_other-task', '{}');
  sessionStorage.setItem('mock_sid', 'teams-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('teamsState_teams-pilot'), null);
  assert.equal(localStorage.getItem('teamsInitialState_teams-pilot'), null);
  assert.equal(localStorage.getItem('teamsState_other-task'), '{}');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
  assert.equal(fetchCalls.length, 0);
});

test('release without a SID rejects and preserves unscoped base state', async () => {
  window.location.search = '';
  localStorage.setItem('teamsState', '{"current":true}');
  localStorage.setItem('teamsInitialState', '{"initial":true}');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /requires a non-empty SID/,
  );
  assert.equal(localStorage.getItem('teamsState'), '{"current":true}');
  assert.equal(localStorage.getItem('teamsInitialState'), '{"initial":true}');
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
