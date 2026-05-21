import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import fs from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { applyEdits, modify, parse } from "jsonc-parser";

const serverDir = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(serverDir, "..");
const repoRoot = path.resolve(appRoot, "..", "..");

const snapshotsRoot = path.join(repoRoot, "snapshots", "__snapshots__");
const seedPath = path.join(
  repoRoot,
  "packages",
  "surfgym-task",
  "src",
  "surfgym_task",
  "data",
  "seed",
  "spreadsheet",
  "seed.jsonc"
);
const instructionPath = path.join(
  repoRoot,
  "packages",
  "surfgym-task",
  "src",
  "surfgym_task",
  "data",
  "seed",
  "spreadsheet",
  "instruction.jsonc"
);

type Manifest = {
  summary: { total: number; reward_sum: number; task_source: string };
  tasks: Record<string, { snapshot_dir: string; reward: number }>;
};

type StateAtom = {
  website_id?: string;
  match?: "contains" | "exact" | "regex";
  normalize_space?: boolean;
  case_sensitive?: boolean;
  value: unknown;
  evalf: string;
  applyf: string;
  param?: string | null;
  property?: string[];
  return_type?: "list" | "obj";
};

type SeedTask = { task_id: string; instruction: string; states: StateAtom[][] };

type InstructionMap = Record<string, string>;

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

function canonicalJson(value: unknown): string {
  if (value === undefined) {
    return "null";
  }

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

  return JSON.stringify(value);
}

function normalizeAtom(atom: StateAtom): Required<StateAtom> {
  return {
    website_id: atom.website_id ?? "_",
    match: atom.match ?? "contains",
    normalize_space: atom.normalize_space ?? false,
    case_sensitive: atom.case_sensitive ?? true,
    value: atom.value,
    evalf: atom.evalf,
    applyf: atom.applyf,
    param: atom.param ?? null,
    property: atom.property ?? [],
    return_type: atom.return_type ?? "obj"
  };
}

function canonicalState(state: StateAtom[]) {
  return state.map(normalizeAtom).sort((left, right) => {
    const leftJson = canonicalJson(left);
    const rightJson = canonicalJson(right);
    return leftJson < rightJson ? -1 : leftJson > rightJson ? 1 : 0;
  });
}

function hoareKey(startState: StateAtom[] | null, endState: StateAtom[]): string {
  const payload = {
    startState: startState === null ? null : canonicalState(startState),
    endState: canonicalState(endState)
  };
  return `hoare:v1:${createHash("sha256").update(canonicalJson(payload), "utf8").digest("hex")}`;
}

function atomFreshnessKey(atom: StateAtom): string {
  return canonicalJson([atom.evalf, atom.param ?? null, atom.property ?? []]);
}

function accumulatedState(states: StateAtom[][], endIndex: number): StateAtom[] {
  const fresh = new Map<string, StateAtom>();
  for (const state of states.slice(0, endIndex + 1)) {
    for (const atom of state) {
      fresh.set(atomFreshnessKey(atom), atom);
    }
  }
  return [...fresh.values()];
}

function parseGeneratedTaskId(taskId: string) {
  const match = /^(.*)_(\d+)_(\d+)$/.exec(taskId);
  if (!match) return null;

  return { seedId: match[1], startOrdinal: Number(match[2]), endOrdinal: Number(match[3]) };
}

function candidateInstructionKeys(seed: SeedTask, startOrdinal: number, endOrdinal: number) {
  const endIndex = endOrdinal - 1;
  const startIndex = startOrdinal > 0 ? startOrdinal - 1 : null;

  if (endIndex < 0 || endIndex >= seed.states.length) {
    return [];
  }

  const deltaStart = startIndex === null ? null : (seed.states[startIndex] ?? null);
  const deltaEnd = seed.states[endIndex];
  const cumulativeStart = startIndex === null ? null : accumulatedState(seed.states, startIndex);
  const cumulativeEnd = accumulatedState(seed.states, endIndex);

  return [hoareKey(deltaStart, deltaEnd), hoareKey(cumulativeStart, cumulativeEnd)];
}

async function buildInstructionResolver(instructions: InstructionMap) {
  const seeds = await readJsonc<SeedTask[]>(seedPath);
  const seedsById = new Map(seeds.map((seed) => [seed.task_id, seed]));
  const directIndex = new Map<string, string>();

  for (const seed of seeds) {
    for (let endIndex = 0; endIndex < seed.states.length; endIndex += 1) {
      const seedTaskId = `${seed.task_id}_0_${endIndex + 1}`;
      const key = hoareKey(null, seed.states[endIndex]);
      directIndex.set(seedTaskId, key);
    }
  }

  return (taskId: string): string | undefined => {
    const existing = directIndex.get(taskId);
    if (existing) return existing;

    const parsed = parseGeneratedTaskId(taskId);
    if (!parsed) return undefined;

    const seed = seedsById.get(parsed.seedId);
    if (!seed) return undefined;

    return candidateInstructionKeys(seed, parsed.startOrdinal, parsed.endOrdinal).find(
      (key) => key in instructions
    );
  };
}

async function readTaskSourceInstructions(taskSource: string): Promise<Map<string, string>> {
  try {
    const rows = await readJsonc<Array<{ task_id: string; instruction?: string }>>(taskSource);
    return new Map(rows.map((row) => [row.task_id, row.instruction ?? ""]));
  } catch {
    return new Map();
  }
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
  const instructions = await readJsonc<InstructionMap>(instructionPath);
  const resolveInstructionKey = await buildInstructionResolver(instructions);
  const sourceInstructions = await readTaskSourceInstructions(manifest.summary.task_source);

  const tasks = await Promise.all(
    Object.entries(manifest.tasks).map(async ([taskId, meta]) => {
      const instructionKey = resolveInstructionKey(taskId) ?? null;
      const taskDir = path.join(runDir, path.basename(String(meta.snapshot_dir)));
      const screenshots = await listScreenshots(taskDir);

      return {
        taskId,
        reward: meta.reward,
        instructionKey,
        instruction: instructionKey
          ? (instructions[instructionKey] ?? "")
          : (sourceInstructions.get(taskId) ?? ""),
        sourceInstruction: sourceInstructions.get(taskId) ?? "",
        screenshots: screenshots.map(
          (file) =>
            `/api/runs/${encodeURIComponent(safeRunId)}/tasks/${encodeURIComponent(taskId)}/screenshots/${encodeURIComponent(file)}`
        )
      };
    })
  );

  return { id: safeRunId, summary: manifest.summary, instructionPath, seedPath, tasks };
}

async function updateInstruction(key: string, instruction: string) {
  const text = await fs.readFile(instructionPath, "utf8");
  const nextText = applyEdits(
    text,
    modify(text, [key], instruction, {
      formattingOptions: { insertSpaces: true, tabSize: 2, eol: "\n" }
    })
  );
  await fs.writeFile(instructionPath, nextText, "utf8");
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
      segments.length === 3 &&
      segments[0] === "api" &&
      segments[1] === "instructions"
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

      await updateInstruction(segments[2], instruction);
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
