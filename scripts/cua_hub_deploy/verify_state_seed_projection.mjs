#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';

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
  if (!args.manifest || !args['seeds-dir'] || !args.report) {
    throw new Error(
      'usage: verify_state_seed_projection.mjs --manifest FILE --seeds-dir DIR --report FILE',
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

function sha256(text) {
  return createHash('sha256').update(text).digest('hex');
}

function baselineState(atoms, file) {
  const state = {};
  for (const [index, atom] of atoms.entries()) {
    const spec = atom?.spec;
    if (spec?.target !== 'app_state' || typeof spec.path !== 'string' || !spec.path) {
      throw new Error(`${file}: states[0][${index}] is not a top-level app_state atom`);
    }
    if (spec.path.includes('.') || Object.hasOwn(state, spec.path)) {
      throw new Error(`${file}: duplicate or nested baseline path ${spec.path}`);
    }
    state[spec.path] = atom.value;
  }
  return state;
}

function evaluateAtom(state, atom, file, index) {
  const script = atom?.spec?.script;
  if (typeof script !== 'string' || !script) {
    throw new Error(`${file}: states[1][${index}] has no script`);
  }
  let observed;
  try {
    observed = Function('state', `"use strict"; return (${script});`)(state);
  } catch (error) {
    throw new Error(`${file}: states[1][${index}] script failed: ${error.message}`);
  }
  return {
    index,
    observed,
    expected: atom.value,
    passed: equal(observed, atom.value),
  };
}

const args = parseArgs(process.argv.slice(2));
const manifestPath = resolve(args.manifest);
const seedsDir = resolve(args['seeds-dir']);
const reportPath = resolve(args.report);
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
if (manifest.version !== 1 || !Array.isArray(manifest.tasks) || manifest.tasks.length === 0) {
  throw new Error(`unsupported projection manifest: ${manifestPath}`);
}

const seedNames = new Set();
const taskIds = new Set();
const results = [];
const perFileHashes = [];
for (const task of [...manifest.tasks].sort((left, right) => left.seed.localeCompare(right.seed))) {
  if (basename(task.seed) !== task.seed || seedNames.has(task.seed)) {
    throw new Error(`invalid or duplicate manifest seed: ${task.seed}`);
  }
  if (typeof task.source_task_id !== 'string' || taskIds.has(task.source_task_id)) {
    throw new Error(`invalid or duplicate source task id: ${task.source_task_id}`);
  }
  seedNames.add(task.seed);
  taskIds.add(task.source_task_id);

  const text = readFileSync(resolve(seedsDir, task.seed), 'utf8');
  const fileHash = sha256(text);
  if (fileHash !== task.seed_sha256) {
    throw new Error(`${task.seed}: seed SHA-256 mismatch`);
  }
  perFileHashes.push(fileHash);
  const seed = JSON.parse(text);
  if (!Array.isArray(seed.states) || seed.states.length !== 2) {
    throw new Error(`${task.seed}: expected exactly two states`);
  }
  const state = baselineState(seed.states[0], task.seed);
  const atoms = seed.states[1].map((atom, index) =>
    evaluateAtom(state, atom, task.seed, index),
  );
  if (seed.states[0].length !== task.initial_atoms || atoms.length !== task.terminal_criteria) {
    throw new Error(`${task.seed}: manifest atom counts do not match`);
  }
  results.push({
    seed: task.seed,
    source_task_id: task.source_task_id,
    sha256: fileHash,
    initial_atoms: seed.states[0].length,
    terminal_criteria: atoms.length,
    initial_success: atoms.every(atom => atom.passed),
    initially_passing_atoms: atoms.filter(atom => atom.passed).length,
    atoms,
  });
}

const aggregateHash = sha256(perFileHashes.join('\n'));
if (aggregateHash !== manifest.aggregate_seed_sha256) {
  throw new Error(`aggregate seed SHA-256 mismatch: ${aggregateHash}`);
}
const initialSuccesses = results.filter(result => result.initial_success);
const checks = {
  seeds: results.length,
  initial_atoms: results.reduce((sum, result) => sum + result.initial_atoms, 0),
  initial_successes: initialSuccesses.length,
  initial_failures: results.length - initialSuccesses.length,
  terminal_criteria: results.reduce((sum, result) => sum + result.terminal_criteria, 0),
  aggregate_seed_sha256: aggregateHash,
};
const status = checks.seeds === manifest.counts.tasks
  && checks.initial_atoms === manifest.counts.initial_atoms
  && checks.terminal_criteria === manifest.counts.terminal_criteria
  && checks.initial_successes === 0
  ? 'PASS'
  : 'FAIL';
const report = {
  version: 1,
  status,
  scope: 'EXPLICIT_CANONICAL_WEB_PROJECTION_INITIAL_STATE',
  manifest: manifestPath,
  checks,
  results,
};
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(JSON.stringify({ status, ...checks }));
if (status !== 'PASS') process.exitCode = 1;
