type PageTarget = "url" | "title" | "text" | "html";

type PageSpec = {
  target: PageTarget;
  selector?: string;
};

type AttributeSpec = {
  target: "attr";
  selector: string;
  attr: string;
};

type ScriptSpec = {
  script: string;
};

type ApiStateSpec = {
  target: "api_state";
  path: string | string[];
};

type ReleaseSpec = {
  $surfgym: {
    type: "release";
  };
};

export type WebStateSpec = PageSpec | AttributeSpec | ScriptSpec | ApiStateSpec | ReleaseSpec;

export type SurfGymBridge = {
  get: (spec: WebStateSpec) => Promise<unknown>;
  set: (spec: WebStateSpec, value: unknown) => Promise<unknown>;
};

declare global {
  interface Window {
    surfgym: SurfGymBridge;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isReleaseSpec(spec: WebStateSpec): spec is ReleaseSpec {
  return (
    "$surfgym" in spec &&
    isRecord(spec.$surfgym) &&
    spec.$surfgym.type === "release"
  );
}

function isScriptSpec(spec: WebStateSpec): spec is ScriptSpec {
  return "script" in spec && typeof spec.script === "string";
}

function normalizePath(path: string | string[]): string[] {
  const parts = Array.isArray(path) ? path : path.split(".");
  if (parts.length === 0 || parts.some((part) => !part.trim())) {
    throw new Error("Web state path must contain non-empty segments.");
  }
  return parts;
}

function readPath(value: unknown, path: string[]): unknown {
  let current = value;
  for (const part of path) {
    if (!isRecord(current)) return undefined;
    current = current[part];
  }
  return current;
}

function nestedPatch(path: string[], value: unknown): Record<string, unknown> {
  let result: unknown = value;
  for (const part of [...path].reverse()) {
    result = { [part]: result };
  }
  return result as Record<string, unknown>;
}

async function requestState(method: "GET" | "PATCH" | "DELETE", body?: object) {
  const response = await fetch("/api/state", {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(`Travel state ${method} failed with HTTP ${response.status}.`);
  }
  return response.json() as Promise<unknown>;
}

function readDom(spec: PageSpec | AttributeSpec): unknown {
  if (!("selector" in spec) || !spec.selector) {
    if (spec.target === "url") return window.location.href;
    if (spec.target === "title") return document.title;
    if (spec.target === "text") return document.body.innerText;
    if (spec.target === "html") return document.documentElement.outerHTML;
    return undefined;
  }

  const element = document.querySelector<HTMLElement>(spec.selector);
  if (!element) return undefined;
  if (spec.target === "text") return element.innerText || element.textContent;
  if (spec.target === "html") return element.outerHTML;
  if (spec.target === "attr") {
    const propertyValue = (element as unknown as Record<string, unknown>)[spec.attr];
    return propertyValue ?? element.getAttribute(spec.attr);
  }
  return undefined;
}

export async function get(spec: WebStateSpec): Promise<unknown> {
  if (!isRecord(spec)) throw new Error("Web state spec must be an object.");

  if (isReleaseSpec(spec)) {
    await requestState("DELETE");
    return true;
  }

  if (isScriptSpec(spec)) {
    const evaluate = eval;
    return evaluate(spec.script) as unknown;
  }

  if (!("target" in spec)) throw new Error("Unsupported web state spec.");
  if (spec.target === "api_state") {
    const payload = await requestState("GET");
    const state = isRecord(payload) ? payload.state : undefined;
    return readPath(state, normalizePath(spec.path));
  }
  if (["url", "title", "text", "html", "attr"].includes(spec.target)) {
    return readDom(spec);
  }
  throw new Error(`Unsupported web state target: ${String(spec.target)}`);
}

export async function set(spec: WebStateSpec, value: unknown): Promise<unknown> {
  if (!isRecord(spec) || !("target" in spec) || spec.target !== "api_state") {
    throw new Error("Only api_state web specs are settable.");
  }

  const [root, ...path] = normalizePath(spec.path);
  if (root !== "data") {
    throw new Error("Web api_state set paths must start with data.");
  }

  const data = path.length === 0 ? value : nestedPatch(path, value);
  return requestState("PATCH", { data });
}

export function installSurfGymBridge(): SurfGymBridge {
  const bridge = { get, set } satisfies SurfGymBridge;
  window.surfgym = bridge;
  return bridge;
}

if (typeof window !== "undefined") installSurfGymBridge();
