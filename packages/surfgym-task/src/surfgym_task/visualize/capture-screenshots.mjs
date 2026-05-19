#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = await findRepoRoot(__dirname);

const defaultInputCandidates = [path.join(repoRoot, "tasks/seed/spreadsheet/out/augmented.json"), path.join(repoRoot, "tasks/seed/spreadsheet/out/augmented.jsonc")];

const defaults = {
  input: null,
  outputDir: path.join(__dirname, "screenshots"),
  dataOut: path.join(__dirname, "data/tasks.json"),
  timeout: 30000,
  settle: 1000,
  width: 1440,
  height: 1000,
  fullPage: true,
  headless: true,
  limit: null,
  only: null,
  slowMo: 0
};

const options = parseArgs(process.argv.slice(2));
const inputPath = options.input ?? (await firstExisting(defaultInputCandidates));

if (!inputPath) {
  console.error("Could not find augmented task file.");
  console.error("Looked for:");
  for (const candidate of defaultInputCandidates) {
    console.error(`  - ${path.relative(repoRoot, candidate)}`);
  }
  console.error("Pass a file explicitly with --input <path>.");
  process.exit(1);
}

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch (error) {
  console.error("Playwright is not installed for this visualization folder.");
  console.error("Run these commands from tasks/visualize:");
  console.error("  pnpm install");
  console.error("  pnpm run install:browsers");
  process.exit(1);
}

await fs.mkdir(options.outputDir, { recursive: true });
await fs.mkdir(path.dirname(options.dataOut), { recursive: true });

const sourceText = await fs.readFile(inputPath, "utf8");
const parsed = parseJsonLike(sourceText, inputPath);
const sourceTasks = normalizeTaskArray(parsed, inputPath);
const filteredTasks = filterTasks(sourceTasks, options);

const manifest = {
  generatedAt: new Date().toISOString(),
  source: { input: path.relative(__dirname, inputPath), taskCount: sourceTasks.length, capturedCount: filteredTasks.length },
  viewport: { width: options.width, height: options.height, fullPage: options.fullPage },
  tasks: []
};

const browserHome = path.join(__dirname, ".browser-home");
await fs.mkdir(browserHome, { recursive: true });

let browser;
try {
  browser = await chromium.launch({ headless: options.headless, slowMo: options.slowMo, env: { ...process.env, HOME: browserHome }, args: ["--disable-crash-reporter", "--disable-crashpad"] });
} catch (error) {
  manifest.error = { stage: "browser.launch", message: formatError(error) };
  await fs.writeFile(options.dataOut, `${JSON.stringify(manifest, null, 2)}\n`);
  console.error(`Failed to launch Chromium: ${formatError(error)}`);
  console.error(`Wrote viewer data: ${path.relative(process.cwd(), options.dataOut)}`);
  process.exit(1);
}

try {
  for (let i = 0; i < filteredTasks.length; i += 1) {
    const task = filteredTasks[i];
    const result = await captureTask(task, i, filteredTasks.length, browser);
    manifest.tasks.push(result);
    const statusText = result.capture.errors.length === 0 ? "ok" : "error";
    console.log(`[${i + 1}/${filteredTasks.length}] ${result.task_id} -> ${result.screenshot} (${statusText})`);
  }
} finally {
  await browser.close();
}

await fs.writeFile(options.dataOut, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Wrote viewer data: ${path.relative(process.cwd(), options.dataOut)}`);

async function captureTask(task, visibleIndex, total, browser) {
  const taskId = String(task.task_id ?? task.id ?? `task_${visibleIndex}`);
  const screenshotName = `${String(visibleIndex + 1).padStart(3, "0")}-${slug(taskId)}.png`;
  const screenshotAbsPath = path.join(options.outputDir, screenshotName);
  const screenshotRelPath = path.relative(__dirname, screenshotAbsPath);
  const capture = { status: "ok", startedAt: new Date().toISOString(), finishedAt: null, pageUrl: null, httpStatus: null, setupRan: false, setupResults: [], errors: [] };

  const context = await browser.newContext({ viewport: { width: options.width, height: options.height } });
  const page = await context.newPage();

  try {
    try {
      const response = await page.goto(task.website, { waitUntil: "domcontentloaded", timeout: options.timeout });
      capture.httpStatus = response?.status() ?? null;

      try {
        await page.waitForLoadState("networkidle", { timeout: Math.min(5000, options.timeout) });
      } catch {
        // Some pages keep long-lived requests open. The explicit settle wait below is enough for capture.
      }
    } catch (error) {
      capture.errors.push(`navigation: ${formatError(error)}`);
      await page.setContent(renderErrorPage(task, capture.errors.at(-1)));
    }

    if (task.setup != null && capture.errors.length === 0) {
      try {
        capture.setupResults = await runSetup(page, task.setup);
        capture.setupRan = capture.setupResults.length > 0;
      } catch (error) {
        capture.errors.push(`setup: ${formatError(error)}`);
      }
    }

    if (options.settle > 0) {
      await page.waitForTimeout(options.settle);
    }

    capture.pageUrl = page.url();
    await page.screenshot({ path: screenshotAbsPath, fullPage: options.fullPage, timeout: options.timeout });
  } catch (error) {
    capture.errors.push(`screenshot: ${formatError(error)}`);
  } finally {
    capture.finishedAt = new Date().toISOString();
    if (capture.errors.length > 0) {
      capture.status = "error";
    }
    await context.close();
  }

  return {
    index: visibleIndex,
    total,
    task_id: taskId,
    website: task.website ?? "",
    instruction: task.instruction ?? "",
    rules: task.rules ?? task.evaluation?.rules ?? [],
    setup: task.setup ?? null,
    screenshot: screenshotRelPath,
    capture,
    task
  };
}

async function runSetup(page, setup) {
  const steps = normalizeSetup(setup);
  const results = [];

  for (const [index, step] of steps.entries()) {
    if (!step.script) {
      results.push({ index, mode: step.mode ?? "unknown", skipped: true, reason: "setup step has no script field" });
      continue;
    }

    const startedAt = Date.now();
    const value = await evaluatePageScript(page, step.script);
    results.push({ index, mode: step.mode ?? "console", skipped: false, durationMs: Date.now() - startedAt, value: makeJsonSafe(value) });
  }

  return results;
}

async function evaluatePageScript(page, script) {
  try {
    return await page.evaluate(script);
  } catch (firstError) {
    try {
      return await page.evaluate((source) => {
        const run = new Function(source);
        return run.call(window);
      }, script);
    } catch (secondError) {
      secondError.message = `${secondError.message} (direct evaluate also failed: ${firstError.message})`;
      throw secondError;
    }
  }
}

function normalizeSetup(setup) {
  if (setup == null) return [];
  if (Array.isArray(setup)) return setup.flatMap((step) => normalizeSetup(step));
  if (typeof setup === "string") return [{ mode: "console", script: setup }];
  if (typeof setup === "object") return [setup];
  return [];
}

function filterTasks(tasks, options) {
  let filtered = tasks.filter((task) => typeof task.website === "string" && task.website.length > 0);

  if (options.only) {
    const selected = new Set(
      options.only
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    );
    filtered = filtered.filter((task) => selected.has(String(task.task_id ?? task.id ?? "")));
  }

  if (options.limit != null) {
    filtered = filtered.slice(0, options.limit);
  }

  return filtered;
}

function parseArgs(argv) {
  const parsed = { ...defaults };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--") continue;

    const [name, inlineValue] = arg.split("=", 2);
    const nextValue = () => inlineValue ?? argv[++i];

    switch (name) {
      case "--input":
        parsed.input = path.resolve(process.cwd(), nextValue());
        break;
      case "--output-dir":
        parsed.outputDir = path.resolve(process.cwd(), nextValue());
        break;
      case "--data-out":
        parsed.dataOut = path.resolve(process.cwd(), nextValue());
        break;
      case "--timeout":
        parsed.timeout = Number(nextValue());
        break;
      case "--settle":
        parsed.settle = Number(nextValue());
        break;
      case "--limit":
        parsed.limit = Number(nextValue());
        break;
      case "--only":
        parsed.only = nextValue();
        break;
      case "--viewport": {
        const [width, height] = nextValue().split("x").map(Number);
        if (!Number.isFinite(width) || !Number.isFinite(height)) {
          throw new Error("--viewport must look like 1440x1000");
        }
        parsed.width = width;
        parsed.height = height;
        break;
      }
      case "--headed":
      case "--headless=false":
        parsed.headless = false;
        break;
      case "--headless":
      case "--headless=true":
        parsed.headless = true;
        break;
      case "--no-full-page":
        parsed.fullPage = false;
        break;
      case "--slow-mo":
        parsed.slowMo = Number(nextValue());
        break;
      case "--help":
      case "-h":
        printHelpAndExit();
        break;
      default:
        throw new Error(`Unknown option: ${arg}`);
    }
  }

  return parsed;
}

function printHelpAndExit() {
  console.log(`
Usage:
  npm run capture -- [options]

Options:
  --input <path>          Task JSON or JSONC file. Defaults to ../tasks/seed/spreadsheet/out/augmented.json, then .jsonc.
  --limit <count>         Capture only the first N tasks.
  --only <ids>            Comma-separated task_id list.
  --viewport <WxH>        Browser viewport. Default: 1440x1000.
  --timeout <ms>          Navigation and screenshot timeout. Default: 30000.
  --settle <ms>           Wait after navigation/setup before screenshot. Default: 1000.
  --headed                Show Chromium while capturing.
  --no-full-page          Capture only the viewport instead of the full page.
`);
  process.exit(0);
}

function parseJsonLike(source, filePath) {
  try {
    return JSON.parse(source);
  } catch {
    try {
      return JSON.parse(stripTrailingCommas(stripJsonComments(source)));
    } catch (error) {
      error.message = `Failed to parse ${filePath}: ${error.message}`;
      throw error;
    }
  }
}

function normalizeTaskArray(parsed, filePath) {
  if (Array.isArray(parsed)) return parsed;
  if (Array.isArray(parsed.tasks)) return parsed.tasks;
  throw new Error(`Expected ${filePath} to contain an array or { "tasks": [...] }.`);
}

function stripJsonComments(source) {
  let output = "";
  let inString = false;
  let quote = "";
  let escaped = false;
  let inLineComment = false;
  let inBlockComment = false;

  for (let i = 0; i < source.length; i += 1) {
    const current = source[i];
    const next = source[i + 1];

    if (inLineComment) {
      if (current === "\n") {
        inLineComment = false;
        output += current;
      }
      continue;
    }

    if (inBlockComment) {
      if (current === "*" && next === "/") {
        inBlockComment = false;
        i += 1;
      }
      continue;
    }

    if (inString) {
      output += current;
      if (escaped) {
        escaped = false;
      } else if (current === "\\") {
        escaped = true;
      } else if (current === quote) {
        inString = false;
      }
      continue;
    }

    if (current === '"' || current === "'") {
      inString = true;
      quote = current;
      output += current;
      continue;
    }

    if (current === "/" && next === "/") {
      inLineComment = true;
      i += 1;
      continue;
    }

    if (current === "/" && next === "*") {
      inBlockComment = true;
      i += 1;
      continue;
    }

    output += current;
  }

  return output;
}

function stripTrailingCommas(source) {
  let output = "";
  let inString = false;
  let quote = "";
  let escaped = false;

  for (let i = 0; i < source.length; i += 1) {
    const current = source[i];

    if (inString) {
      output += current;
      if (escaped) {
        escaped = false;
      } else if (current === "\\") {
        escaped = true;
      } else if (current === quote) {
        inString = false;
      }
      continue;
    }

    if (current === '"' || current === "'") {
      inString = true;
      quote = current;
      output += current;
      continue;
    }

    if (current === ",") {
      let j = i + 1;
      while (/\s/.test(source[j] ?? "")) j += 1;
      if (source[j] === "}" || source[j] === "]") continue;
    }

    output += current;
  }

  return output;
}

async function firstExisting(paths) {
  for (const candidate of paths) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // Try the next default path.
    }
  }
  return null;
}

async function findRepoRoot(startDir) {
  let dir = startDir;

  while (true) {
    const hasAugmentedTasks = await firstExisting([
      path.join(dir, "tasks/seed/spreadsheet/out/augmented.json"),
      path.join(dir, "tasks/seed/spreadsheet/out/augmented.jsonc"),
    ]);

    if (hasAugmentedTasks) return dir;

    const parent = path.dirname(dir);
    if (parent === dir) return path.resolve(startDir, "..");
    dir = parent;
  }
}

function renderErrorPage(task, message) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Capture failed</title>
    <style>
      body { margin: 0; font-family: system-ui, sans-serif; background: #f8fafc; color: #172033; }
      main { max-width: 900px; margin: 56px auto; padding: 32px; border: 1px solid #d5dce8; background: #fff; border-radius: 8px; }
      h1 { margin-top: 0; font-size: 24px; }
      code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
      pre { white-space: pre-wrap; background: #f1f5f9; padding: 16px; border-radius: 8px; }
    </style>
  </head>
  <body>
    <main>
      <h1>Capture failed before the page was ready</h1>
      <p><strong>Task:</strong> ${escapeHtml(String(task.task_id ?? task.id ?? "unknown"))}</p>
      <p><strong>Website:</strong> ${escapeHtml(String(task.website ?? ""))}</p>
      <pre>${escapeHtml(message)}</pre>
    </main>
  </body>
</html>`;
}

function slug(value) {
  return (
    String(value)
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 96) || "task"
  );
}

function formatError(error) {
  return error instanceof Error ? error.message : String(error);
}

function makeJsonSafe(value) {
  if (value == null) return value;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return String(value);
  }
}

function escapeHtml(value) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
