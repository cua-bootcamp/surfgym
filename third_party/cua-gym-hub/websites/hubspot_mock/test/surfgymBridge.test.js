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
globalThis.window = { location: { search: '?sid=hubspot-pilot' } };
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  return { ok: true, json: async () => ({}) };
};

const { get, set } = await import('../src/surfgymBridge.js');

beforeEach(() => {
  fetchCalls.length = 0;
  localStorage.clear();
  sessionStorage.clear();
  window.location.search = '?sid=hubspot-pilot';
});

test('installs the SurfGym bridge on the app window', () => {
  assert.equal(window.surfgym.get, get);
  assert.equal(window.surfgym.set, set);
});

test('writes through canonical saveState without replacing siblings', async () => {
  localStorage.setItem(
    'hubspot_mock_db_hubspot-pilot',
    JSON.stringify({
      contacts: [{ id: 'contact-1', firstName: 'Alice' }],
      appState: { sidebarOpen: true },
    }),
  );

  await set({ target: 'app_state', path: 'contacts.0.firstName' }, 'Alicia');
  await new Promise(resolve => setTimeout(resolve, 350));

  assert.equal(
    await get({ target: 'app_state', path: ['contacts', '0', 'firstName'] }),
    'Alicia',
  );
  assert.equal(
    Array.isArray(await get({ target: 'app_state', path: 'contacts' })),
    true,
  );
  assert.equal(
    await get({ target: 'app_state', path: 'appState.sidebarOpen' }),
    true,
  );
  assert.equal(fetchCalls.at(-1).url, '/post?sid=hubspot-pilot');
  assert.equal(
    JSON.parse(fetchCalls.at(-1).options.body).action,
    'set_current',
  );
});

test('evaluates trusted checked-in criteria scripts', async () => {
  localStorage.setItem(
    'hubspot_mock_db_hubspot-pilot',
    JSON.stringify({ deals: [{ id: 'deal-1', stage: 'closed_won' }] }),
  );

  assert.equal(
    await get({ script: "state.deals.some(deal => deal.stage === 'closed_won')" }),
    true,
  );
});

test('release is SID-exact and preserves the app-owned serverSeeded marker', async () => {
  localStorage.setItem('hubspot_mock_db_hubspot-pilot', '{}');
  localStorage.setItem('hubspot_mock_db_initial_hubspot-pilot', '{}');
  localStorage.setItem(
    'hubspot_mock_db_initial_serverSeeded_hubspot-pilot',
    'true',
  );
  localStorage.setItem('hubspot_mock_db_other-task', '{}');
  sessionStorage.setItem('mock_sid', 'hubspot-pilot');

  assert.equal(await get({ $surfgym: { type: 'release' } }), true);
  assert.equal(localStorage.getItem('hubspot_mock_db_hubspot-pilot'), null);
  assert.equal(
    localStorage.getItem('hubspot_mock_db_initial_hubspot-pilot'),
    null,
  );
  assert.equal(
    localStorage.getItem(
      'hubspot_mock_db_initial_serverSeeded_hubspot-pilot',
    ),
    'true',
  );
  assert.equal(localStorage.getItem('hubspot_mock_db_other-task'), '{}');
  assert.equal(sessionStorage.getItem('mock_sid'), null);
  assert.equal(fetchCalls.length, 0);
});

test('release rejects a missing SID and preserves unscoped state', async () => {
  window.location.search = '';
  sessionStorage.clear();
  localStorage.setItem('hubspot_mock_db', 'base-current');
  localStorage.setItem('hubspot_mock_db_initial', 'base-initial');

  await assert.rejects(
    () => get({ $surfgym: { type: 'release' } }),
    /non-empty session ID/,
  );
  assert.equal(localStorage.getItem('hubspot_mock_db'), 'base-current');
  assert.equal(localStorage.getItem('hubspot_mock_db_initial'), 'base-initial');
});

test('rejects unsupported state specs', async () => {
  await assert.rejects(() => get({ target: 'url' }), /Unsupported web state spec/);
  await assert.rejects(() => set({ target: 'url' }, '/next'), /Only app_state/);
});
