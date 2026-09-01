import {
  getSessionId,
  initialKey,
  saveState,
  storageKey,
} from './utils/storage.js';

const CHAT_BACKGROUND_PREFIX = 'wechat_chat_bg';
const SESSION_KEY = 'mock_sid';

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isReleaseSpec(spec) {
  return (
    isRecord(spec) &&
    isRecord(spec.$surfgym) &&
    spec.$surfgym.type === 'release'
  );
}

function requireSessionId() {
  const sid = getSessionId();
  if (!sid) throw new Error('WeChat session ID is unavailable.');
  return sid;
}

function normalizePath(path) {
  const parts = Array.isArray(path) ? path : String(path || '').split('.');
  if (parts.length === 0 || parts.some(part => !String(part).trim())) {
    throw new Error('Web state path must contain non-empty segments.');
  }
  return parts;
}

function readStoredState(sid) {
  const stored = localStorage.getItem(storageKey(sid));
  return stored ? JSON.parse(stored) : null;
}

async function waitForState(sid) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const state = readStoredState(sid);
    if (state) return state;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error('WeChat app state was unavailable.');
}

function readPath(state, path) {
  let current = state;
  for (const part of path) {
    if (!isRecord(current)) return undefined;
    current = current[part];
  }
  return current;
}

function replacePath(state, path, value) {
  const result = { ...state };
  let source = state;
  let target = result;
  for (const part of path.slice(0, -1)) {
    const child = isRecord(source?.[part]) ? source[part] : {};
    target[part] = { ...child };
    source = child;
    target = target[part];
  }
  target[path.at(-1)] = value;
  return result;
}

function removeChatBackgrounds(sid) {
  const prefix = `${CHAT_BACKGROUND_PREFIX}_${sid}_`;
  const keysToRemove = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key?.startsWith(prefix)) keysToRemove.push(key);
  }
  keysToRemove.forEach(key => localStorage.removeItem(key));
}

function releaseSessionState(sid) {
  localStorage.removeItem(storageKey(sid));
  localStorage.removeItem(initialKey(sid));
  removeChatBackgrounds(sid);
  if (sessionStorage.getItem(SESSION_KEY) === sid) {
    sessionStorage.removeItem(SESSION_KEY);
  }
}

export async function get(spec) {
  if (!isRecord(spec)) throw new Error('Web state spec must be an object.');

  const sid = requireSessionId();
  if (isReleaseSpec(spec)) {
    releaseSessionState(sid);
    return true;
  }

  const isScript = typeof spec.script === 'string';
  if (!isScript && spec.target !== 'app_state') {
    throw new Error('Unsupported web state spec.');
  }

  const state = await waitForState(sid);
  if (isScript) {
    return Function('state', `"use strict"; return (${spec.script});`)(state);
  }
  return readPath(state, normalizePath(spec.path));
}

export async function set(spec, value) {
  if (!isRecord(spec) || spec.target !== 'app_state') {
    throw new Error('Only app_state web specs are settable.');
  }

  const sid = requireSessionId();
  const state = await waitForState(sid);
  const updated = replacePath(state, normalizePath(spec.path), value);
  saveState(updated, sid);
  return value;
}

export function installSurfGymBridge() {
  const bridge = { get, set };
  window.surfgym = bridge;
  return bridge;
}

if (typeof window !== 'undefined') installSurfGymBridge();
