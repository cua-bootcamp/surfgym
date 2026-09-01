#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { isAbsolute, relative, resolve, sep } from 'node:path';

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || value === undefined) {
      throw new Error(`invalid arguments near ${key ?? '<end>'}`);
    }
    args[key.slice(2)] = value;
  }
  if (
    !args.manifest
    || !args.map
    || !args['evidence-root']
    || !args['seeds-dir']
    || !args.report
  ) {
    throw new Error(
      'usage: verify_state_seed_reference_replay.mjs --manifest FILE --map FILE '
      + '--evidence-root DIR --seeds-dir DIR --report FILE',
    );
  }
  return args;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}

function equal(left, right) {
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

function loadState(path) {
  const payload = JSON.parse(readFileSync(path, 'utf8'));
  const observation = Array.isArray(payload?.observation) ? payload.observation[0] : payload?.observation;
  return observation?.current_state ?? payload?.current_state ?? payload?.stored_state ?? payload;
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function assertEvidenceDescendant(evidenceRoot, path, label) {
  const child = relative(evidenceRoot, path);
  if (!child || child === '..' || child.startsWith(`..${sep}`) || isAbsolute(child)) {
    throw new Error(`${label} is outside evidence root: ${path}`);
  }
}

function resolveEvidencePath(evidenceRoot, value) {
  if (isAbsolute(value)) {
    throw new Error(`state evidence path must be relative to evidence root: ${value}`);
  }
  if (value.split(/[\\/]/).includes('..')) {
    throw new Error(`state evidence path must not contain '..': ${value}`);
  }
  const path = realpathSync(resolve(evidenceRoot, value));
  assertEvidenceDescendant(evidenceRoot, path, 'state evidence path');
  return path;
}

const args = parseArgs(process.argv.slice(2));
const manifestPath = resolve(args.manifest);
const evidenceRoot = realpathSync(resolve(args['evidence-root']));
const mapPath = realpathSync(resolve(args.map));
const seedsDir = resolve(args['seeds-dir']);
assertEvidenceDescendant(evidenceRoot, mapPath, 'reference replay map');
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const pinnedMapHash = manifest?.evidence?.reference_replay_map_sha256;
if (typeof pinnedMapHash !== 'string' || !/^[0-9a-f]{64}$/.test(pinnedMapHash)) {
  throw new Error('manifest evidence.reference_replay_map_sha256 is missing or invalid');
}
const actualMapHash = sha256File(mapPath);
if (actualMapHash !== pinnedMapHash) {
  throw new Error(
    `reference replay map SHA-256 mismatch: expected ${pinnedMapHash}, got ${actualMapHash}`,
  );
}
const evidenceMap = JSON.parse(readFileSync(mapPath, 'utf8'));
const manifestById = new Map(manifest.tasks.map(task => [task.source_task_id, task]));
if (manifestById.size !== manifest.tasks.length) {
  throw new Error('manifest source task IDs must be unique');
}

const mappedEntries = (evidenceMap.tasks ?? []).filter(
  entry => typeof entry.state_path === 'string' && entry.state_path,
);
const mappedIds = new Set(mappedEntries.map(entry => entry.task_id));
const expectedIds = new Set(manifestById.keys());
if (mappedIds.size !== expectedIds.size || [...expectedIds].some(taskId => !mappedIds.has(taskId))) {
  throw new Error('reference map task IDs do not match the explicit manifest cohort');
}

const results = [];
for (const entry of mappedEntries) {
  const task = manifestById.get(entry.task_id);
  const seedPath = resolve(seedsDir, task.seed);
  const statePath = resolveEvidencePath(evidenceRoot, entry.state_path);
  const seed = JSON.parse(readFileSync(seedPath, 'utf8'));
  const state = loadState(statePath);
  const atoms = seed.states[1].map((atom, index) => {
    try {
      const observed = Function('state', `"use strict"; return (${atom.spec.script});`)(state);
      return { index, observed, expected: atom.value, passed: equal(observed, atom.value) };
    } catch (error) {
      return { index, passed: false, error: error.message };
    }
  });
  results.push({
    task_id: entry.task_id,
    seed: task.seed,
    state_path: statePath,
    terminal_criteria: atoms.length,
    passed: atoms.every(atom => atom.passed),
    atoms,
  });
}

const failures = results.filter(result => !result.passed);
const checks = {
  mapped_tasks: results.length,
  missing_tasks: expectedIds.size - results.length,
  passing_tasks: results.length - failures.length,
  failing_tasks: failures.length,
  terminal_criteria: results.reduce((sum, result) => sum + result.terminal_criteria, 0),
};
const status = checks.mapped_tasks === manifest.counts.tasks
  && checks.missing_tasks === 0
  && checks.failing_tasks === 0
  && checks.terminal_criteria === manifest.counts.terminal_criteria
  ? 'PASS'
  : 'FAIL';
const report = {
  version: 1,
  status,
  evidence_class: 'HISTORICAL_REFERENCE_REPLAY_NOT_CURRENT_HEADED_ACCEPTANCE',
  manifest: manifestPath,
  map: mapPath,
  checks,
  results,
};
writeFileSync(resolve(args.report), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(JSON.stringify({ status, ...checks }));
if (status !== 'PASS') process.exitCode = 1;
