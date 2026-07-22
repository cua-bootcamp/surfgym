import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import fs from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";

import { parse } from "jsonc-parser";

const serverDir = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(serverDir, "..");
const repoRoot = path.resolve(appRoot, "..", "..");

const snapshotsRoot = path.join(repoRoot, "snapshots", "__snapshots__");
const defaultTaskSourcePath = path.join(
  repoRoot,
  "packages",
  "surfgym-task",
  "src",
  "surfgym_task",
  "data",
  "spreadsheet",
  "out",
  "tasks.sqlite3"
);

type Manifest = {
  summary: { total: number; reward_sum: number; task_source: string };
  tasks: Record<string, { snapshot_dir: string; reward: number }>;
};

type TaskDatabaseRow = { task_id: unknown; payload: unknown };
type InstructionDatabaseRow = { task_hash: unknown; instruction: unknown };
type TaskSourceEntry = { instruction: string };
type InstructionMap = Map<string, string>;

type StateAtom = {
  website_id?: unknown;
  match?: unknown;
  normalize_space?: unknown;
  case_sensitive?: unknown;
  value?: unknown;
  spec?: unknown;
};

type RawSeedTask = {
  states?: unknown;
  domain?: unknown;
  empty_start?: unknown;
  accumulation?: unknown;
};

type NormalizedSeedTask = { states: StateAtom[][]; accumulation: "DELTA" | "CUMULATIVE" };
type SeedCache = Map<string, Promise<NormalizedSeedTask | null>>;

const jsonHeaders = { "content-type": "application/json; charset=utf-8" };

function sendJson(response: ServerResponse, status: number, payload: unknown) {
  response.writeHead(status, jsonHeaders);
  response.end(JSON.stringify(payload));
}

function sendError(response: ServerResponse, status: number, message: string) {
  sendJson(response, status, { error: message });
}

async function readRequestJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const body = Buffer.concat(chunks).toString("utf8").trim();
  return body ? JSON.parse(body) : {};
}

async function readJsonc<T>(filePath: string): Promise<T> {
  const text = await fs.readFile(filePath, "utf8");
  return parse(text) as T;
}

function resolveTaskSourcePath(taskSource: string): string {
  const candidate = taskSource.trim() || defaultTaskSourcePath;
  return path.isAbsolute(candidate) ? candidate : path.resolve(repoRoot, candidate);
}

function resolveInstructionDatabasePath(taskSourcePath: string): string {
  if (path.extname(taskSourcePath) !== ".sqlite3") {
    throw new Error(`Snapshot task source is not a SQLite database: ${taskSourcePath}`);
  }

  return path.resolve(path.dirname(taskSourcePath), "..", "instructions.sqlite3");
}

async function assertRegularFile(filePath: string, label: string) {
  const stat = await fs.stat(filePath).catch(() => null);
  if (!stat?.isFile()) {
    throw new Error(`${label} not found: ${filePath}`);
  }
}

async function readTaskSourceTasks(taskSourcePath: string): Promise<Map<string, TaskSourceEntry>> {
  await assertRegularFile(taskSourcePath, "Task database");
  const database = new DatabaseSync(taskSourcePath, { readOnly: true });

  try {
    const rows = database
      .prepare("SELECT task_id, payload FROM tasks ORDER BY rowid")
      .all() as TaskDatabaseRow[];
    const tasks = new Map<string, TaskSourceEntry>();

    for (const row of rows) {
      if (typeof row.task_id !== "string" || typeof row.payload !== "string") continue;

      const payload = JSON.parse(row.payload) as { instruction?: unknown };
      tasks.set(row.task_id, {
        instruction: typeof payload.instruction === "string" ? payload.instruction : ""
      });
    }

    return tasks;
  } finally {
    database.close();
  }
}

async function readInstructionMap(instructionDatabasePath: string): Promise<InstructionMap> {
  await assertRegularFile(instructionDatabasePath, "Instruction database");
  const database = new DatabaseSync(instructionDatabasePath, { readOnly: true });

  try {
    const rows = database
      .prepare("SELECT task_hash, instruction FROM instructions ORDER BY rowid")
      .all() as InstructionDatabaseRow[];
    const instructions: InstructionMap = new Map();

    for (const row of rows) {
      if (typeof row.task_hash === "string" && typeof row.instruction === "string") {
        instructions.set(row.task_hash, row.instruction);
      }
    }

    return instructions;
  } finally {
    database.close();
  }
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }

  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }

  const serialized = JSON.stringify(value);
  if (serialized === undefined) {
    throw new Error("Seed contains a value that cannot be serialized.");
  }
  return serialized;
}

function isStateAtom(value: unknown): value is StateAtom {
  if (value === null || typeof value !== "object") return false;
  const atom = value as StateAtom;
  return atom.spec !== null && typeof atom.spec === "object" && "value" in atom;
}

function normalizeSeed(rawSeed: RawSeedTask, targetDirectory: string): NormalizedSeedTask {
  if (!Array.isArray(rawSeed.states)) {
    throw new Error("Seed states must be an array.");
  }

  const states = rawSeed.states.map((state) => {
    if (!Array.isArray(state) || !state.every(isStateAtom)) {
      throw new Error("Seed contains a state atom without a spec and value.");
    }
    return [...state];
  });

  const domain =
    typeof rawSeed.domain === "string" ? rawSeed.domain : path.basename(targetDirectory);
  if ((domain === "spreadsheet" || domain === "word") && rawSeed.empty_start === true) {
    states.unshift([]);
  } else if (domain === "impress") {
    // SeedReader currently inserts an empty start for Impress even when empty_start is false.
    states.unshift([]);
  }

  return { states, accumulation: rawSeed.accumulation === "DELTA" ? "DELTA" : "CUMULATIVE" };
}

function normalizedAtom(atom: StateAtom) {
  return {
    website_id: typeof atom.website_id === "string" ? atom.website_id : "_",
    match:
      atom.match === "contains" || atom.match === "regex" || atom.match === "exact"
        ? atom.match
        : "exact",
    normalize_space: typeof atom.normalize_space === "boolean" ? atom.normalize_space : false,
    case_sensitive: typeof atom.case_sensitive === "boolean" ? atom.case_sensitive : true,
    value: atom.value,
    spec: atom.spec
  };
}

function accumulatedState(
  states: StateAtom[][],
  index: number,
  accumulation: "DELTA" | "CUMULATIVE"
): StateAtom[] {
  if (accumulation === "DELTA") return states[index] ?? [];

  const fresh = new Map<string, StateAtom>();
  for (const state of states.slice(0, index + 1)) {
    for (const atom of state) {
      fresh.set(canonicalJson(atom.spec), atom);
    }
  }
  return [...fresh.values()];
}

function parseGeneratedTaskId(taskId: string) {
  const match = /^(.*)_(\d+)_(\d+)$/.exec(taskId);
  if (!match) return null;
  return { seedName: match[1], startIndex: Number(match[2]), endIndex: Number(match[3]) };
}

function loadSeed(
  seedName: string,
  targetDirectory: string,
  seedCache: SeedCache
): Promise<NormalizedSeedTask | null> {
  const cached = seedCache.get(seedName);
  if (cached) return cached;

  const seedPath = path.join(targetDirectory, "seeds", `${seedName}.json`);
  const pending = readJsonc<RawSeedTask>(seedPath)
    .then((rawSeed) => normalizeSeed(rawSeed, targetDirectory))
    .catch(() => null);
  seedCache.set(seedName, pending);
  return pending;
}

async function calculateTaskHash(
  taskId: string,
  targetDirectory: string,
  seedCache: SeedCache
): Promise<string | null> {
  const parsedTaskId = parseGeneratedTaskId(taskId);
  if (!parsedTaskId) return null;

  const seed = await loadSeed(parsedTaskId.seedName, targetDirectory, seedCache);
  if (!seed) return null;
  if (
    parsedTaskId.startIndex < 0 ||
    parsedTaskId.endIndex <= parsedTaskId.startIndex ||
    parsedTaskId.endIndex >= seed.states.length
  ) {
    return null;
  }

  const payload = {
    origin_start_idx: parsedTaskId.startIndex,
    origin_end_idx: parsedTaskId.endIndex,
    start_state: accumulatedState(seed.states, parsedTaskId.startIndex, seed.accumulation).map(
      normalizedAtom
    ),
    end_state: accumulatedState(seed.states, parsedTaskId.endIndex, seed.accumulation).map(
      normalizedAtom
    )
  };

  return createHash("sha256").update(canonicalJson(payload), "utf8").digest("hex");
}

function instructionKeyByUniqueText(
  sourceInstruction: string,
  instructions: InstructionMap
): string | null {
  const matches = [...instructions.entries()].filter(([, instruction]) => {
    return instruction === sourceInstruction;
  });
  return matches.length === 1 ? matches[0][0] : null;
}

async function resolveInstructionKey(
  taskId: string,
  sourceInstruction: string,
  targetDirectory: string,
  instructions: InstructionMap,
  seedCache: SeedCache
): Promise<string | null> {
  const calculatedHash = await calculateTaskHash(taskId, targetDirectory, seedCache).catch(
    () => null
  );
  if (calculatedHash && instructions.has(calculatedHash)) return calculatedHash;
  return instructionKeyByUniqueText(sourceInstruction, instructions);
}

async function listRuns() {
  const entries = await fs.readdir(snapshotsRoot, { withFileTypes: true }).catch(() => []);
  const runs = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    try {
      const manifest = await readManifest(entry.name);
      runs.push({ id: entry.name, summary: manifest.summary });
    } catch {
      continue;
    }
  }

  return runs.sort((left, right) => right.id.localeCompare(left.id));
}

async function readManifest(runId: string): Promise<Manifest> {
  return readJsonc<Manifest>(path.join(snapshotsRoot, path.basename(runId), "manifest.json"));
}

async function listScreenshots(taskDir: string): Promise<string[]> {
  const entries = await fs.readdir(taskDir).catch(() => []);
  return entries
    .filter((entry) => /^screenshot_\d+\.png$/.test(entry))
    .sort(
      (left, right) => Number(left.match(/\d+/)?.[0] ?? 0) - Number(right.match(/\d+/)?.[0] ?? 0)
    );
}

async function runDetail(runId: string) {
  const safeRunId = path.basename(runId);
  const runDir = path.join(snapshotsRoot, safeRunId);
  const manifest = await readManifest(safeRunId);
  const taskSourcePath = resolveTaskSourcePath(manifest.summary.task_source);
  const instructionPath = resolveInstructionDatabasePath(taskSourcePath);
  const targetDirectory = path.dirname(path.dirname(taskSourcePath));
  const [sourceTasks, instructions] = await Promise.all([
    readTaskSourceTasks(taskSourcePath),
    readInstructionMap(instructionPath)
  ]);
  const seedCache: SeedCache = new Map();

  const tasks = await Promise.all(
    Object.entries(manifest.tasks).map(async ([taskId, meta]) => {
      const sourceTask = sourceTasks.get(taskId);
      const sourceInstruction = sourceTask?.instruction ?? "";
      const instructionKey = await resolveInstructionKey(
        taskId,
        sourceInstruction,
        targetDirectory,
        instructions,
        seedCache
      );
      const taskDir = path.join(runDir, path.basename(String(meta.snapshot_dir)));
      const screenshots = await listScreenshots(taskDir);

      return {
        taskId,
        reward: meta.reward,
        instructionKey,
        instruction: instructionKey
          ? (instructions.get(instructionKey) ?? sourceInstruction)
          : sourceInstruction,
        sourceInstruction,
        screenshots: screenshots.map(
          (file) =>
            `/api/runs/${encodeURIComponent(safeRunId)}/tasks/${encodeURIComponent(taskId)}/screenshots/${encodeURIComponent(file)}`
        )
      };
    })
  );

  return { id: safeRunId, summary: manifest.summary, instructionPath, taskSourcePath, tasks };
}

async function updateInstruction(
  runId: string,
  key: string,
  instruction: string
): Promise<boolean> {
  const manifest = await readManifest(runId);
  const taskSourcePath = resolveTaskSourcePath(manifest.summary.task_source);
  const instructionPath = resolveInstructionDatabasePath(taskSourcePath);
  await assertRegularFile(instructionPath, "Instruction database");

  const database = new DatabaseSync(instructionPath);
  try {
    database.exec("PRAGMA busy_timeout = 5000");
    const result = database
      .prepare("UPDATE instructions SET instruction = ? WHERE task_hash = ?")
      .run(instruction, key);
    return Number(result.changes) > 0;
  } finally {
    database.close();
  }
}

async function serveScreenshot(
  response: ServerResponse,
  runId: string,
  taskId: string,
  file: string
) {
  const safeFile = path.basename(file);
  if (!/^screenshot_\d+\.png$/.test(safeFile)) {
    sendError(response, 400, "Invalid screenshot file.");
    return;
  }

  const filePath = path.join(snapshotsRoot, path.basename(runId), path.basename(taskId), safeFile);
  try {
    await fs.stat(filePath);
  } catch {
    sendError(response, 404, "Screenshot not found.");
    return;
  }

  response.writeHead(200, { "content-type": "image/png" });
  createReadStream(filePath).pipe(response);
}

async function handleRequest(request: IncomingMessage, response: ServerResponse) {
  try {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const segments = url.pathname.split("/").filter(Boolean).map(decodeURIComponent);

    if (request.method === "GET" && url.pathname === "/api/runs") {
      sendJson(response, 200, await listRuns());
      return;
    }

    if (
      request.method === "GET" &&
      segments.length === 3 &&
      segments[0] === "api" &&
      segments[1] === "runs"
    ) {
      sendJson(response, 200, await runDetail(segments[2]));
      return;
    }

    if (
      request.method === "GET" &&
      segments.length === 7 &&
      segments[0] === "api" &&
      segments[1] === "runs" &&
      segments[3] === "tasks" &&
      segments[5] === "screenshots"
    ) {
      await serveScreenshot(response, segments[2], segments[4], segments[6]);
      return;
    }

    if (
      request.method === "PATCH" &&
      segments.length === 5 &&
      segments[0] === "api" &&
      segments[1] === "runs" &&
      segments[3] === "instructions"
    ) {
      const body = await readRequestJson(request);
      const instruction =
        typeof body === "object" && body !== null && "instruction" in body
          ? String((body as { instruction: unknown }).instruction).trim()
          : "";

      if (!instruction) {
        sendError(response, 400, "Instruction is required.");
        return;
      }

      const updated = await updateInstruction(segments[2], segments[4], instruction);
      if (!updated) {
        sendError(response, 404, "Instruction hash not found.");
        return;
      }

      sendJson(response, 200, { instruction });
      return;
    }

    sendError(response, 404, "Not found.");
  } catch (error) {
    sendError(response, 500, error instanceof Error ? error.message : "Unexpected error.");
  }
}

createServer((request, response) => {
  void handleRequest(request, response);
}).listen(5178, "127.0.0.1", () => {
  console.log("snapshot visualize api: http://127.0.0.1:5178");
});
