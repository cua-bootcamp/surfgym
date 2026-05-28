import { createReadStream } from "node:fs";
import fs from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { parse } from "jsonc-parser";

const serverDir = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(serverDir, "..");
const repoRoot = path.resolve(appRoot, "..", "..");

const snapshotsRoot = path.join(repoRoot, "snapshots", "__snapshots__");
const augmentedPath = path.join(
  repoRoot,
  "packages",
  "surfgym-task",
  "src",
  "surfgym_task",
  "data",
  "spreadsheet",
  "out",
  "augmented.jsonl"
);
const instructionPath = path.join(
  repoRoot,
  "packages",
  "surfgym-task",
  "src",
  "surfgym_task",
  "data",
  "spreadsheet",
  "instruction.jsonl"
);

type Manifest = {
  summary: { total: number; reward_sum: number; task_source: string };
  tasks: Record<string, { snapshot_dir: string; reward: number }>;
};

type AugmentedTask = { task_id: string; instruction?: string; hash?: string };
type TaskSourceEntry = { instruction: string; hash: string | null };
type InstructionRow = { hash?: unknown; instruction?: unknown };

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

async function readJsonl<T>(filePath: string): Promise<T[]> {
  const text = await fs.readFile(filePath, "utf8");
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as T);
}

async function readInstructionMap(): Promise<InstructionMap> {
  const rows = await readJsonl<InstructionRow>(instructionPath).catch(() => []);
  const instructions: InstructionMap = {};

  for (const row of rows) {
    if (typeof row.hash === "string" && typeof row.instruction === "string") {
      instructions[row.hash] = row.instruction;
    }
  }

  return instructions;
}

async function writeInstructionMap(instructions: InstructionMap) {
  const rows = Object.entries(instructions)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([hash, instruction]) => JSON.stringify({ hash, instruction }));

  await fs.writeFile(instructionPath, `${rows.join("\n")}${rows.length > 0 ? "\n" : ""}`, "utf8");
}

async function readTaskSourceTasks(taskSource: string): Promise<Map<string, TaskSourceEntry>> {
  try {
    const rows = taskSource.endsWith(".jsonl")
      ? await readJsonl<AugmentedTask>(taskSource)
      : await readJsonc<AugmentedTask[]>(taskSource);

    return new Map(
      rows.map((row) => [
        row.task_id,
        { instruction: row.instruction ?? "", hash: typeof row.hash === "string" ? row.hash : null }
      ])
    );
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
  const instructions = await readInstructionMap();
  const taskSourcePath = manifest.summary.task_source || augmentedPath;
  const sourceTasks = await readTaskSourceTasks(taskSourcePath);

  const tasks = await Promise.all(
    Object.entries(manifest.tasks).map(async ([taskId, meta]) => {
      const sourceTask = sourceTasks.get(taskId);
      const instructionKey = sourceTask?.hash ?? null;
      const taskDir = path.join(runDir, path.basename(String(meta.snapshot_dir)));
      const screenshots = await listScreenshots(taskDir);

      return {
        taskId,
        reward: meta.reward,
        instructionKey,
        instruction: instructionKey
          ? (instructions[instructionKey] ?? sourceTask?.instruction ?? "")
          : (sourceTask?.instruction ?? ""),
        sourceInstruction: sourceTask?.instruction ?? "",
        screenshots: screenshots.map(
          (file) =>
            `/api/runs/${encodeURIComponent(safeRunId)}/tasks/${encodeURIComponent(taskId)}/screenshots/${encodeURIComponent(file)}`
        )
      };
    })
  );

  return { id: safeRunId, summary: manifest.summary, instructionPath, taskSourcePath, tasks };
}

async function updateInstruction(key: string, instruction: string) {
  const instructions = await readInstructionMap();
  instructions[key] = instruction;
  await writeInstructionMap(instructions);
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
