export const SESSION_FINALIZATION_MARKER_CAPACITY = 4096;
export const SESSION_FINALIZATION_RETRY_HORIZON_MS = 15 * 60 * 1000;

type LifecyclePhase = "closing" | "closed" | "failed";

interface Marker {
  phase: LifecyclePhase;
  closedAt?: number;
  pending?: Promise<unknown>;
  result?: unknown;
}

const markers = new Map<string, Marker>();
const queues = new Map<string, Promise<void>>();
let nowForTests: (() => number) | undefined;

function now(): number {
  return nowForTests?.() ?? Date.now();
}

export class SessionFinalizedError extends Error {
  constructor() {
    super("This SurfGym session has been finalized");
    this.name = "SessionFinalizedError";
  }
}

export class SessionLifecycleCapacityError extends Error {
  constructor() {
    super("SurfGym finalization marker capacity is exhausted");
    this.name = "SessionLifecycleCapacityError";
  }
}

function pruneExpiredMarkers(): void {
  const cutoff = now() - SESSION_FINALIZATION_RETRY_HORIZON_MS;
  for (const [key, marker] of markers) {
    if (marker.phase === "closed" && marker.closedAt !== undefined && marker.closedAt <= cutoff) {
      markers.delete(key);
    }
  }
}

function isMarked(key: string): boolean {
  pruneExpiredMarkers();
  return markers.has(key);
}

function rememberClosed(key: string, result: unknown): void {
  markers.set(key, { phase: "closed", closedAt: now(), result });
}

async function enqueue<T>(key: string, operation: () => Promise<T>): Promise<T> {
  const previous = queues.get(key) ?? Promise.resolve();
  let release!: () => void;
  const current = new Promise<void>((resolve) => {
    release = resolve;
  });
  const tail = previous.then(() => current, () => current);
  queues.set(key, tail);

  try {
    await previous;
    return await operation();
  } finally {
    release();
    if (queues.get(key) === tail) {
      queues.delete(key);
    }
  }
}

/** Serialize an ordinary state or file operation for one cookie key. */
export async function withOpenSession<T>(
  key: string,
  operation: () => Promise<T>
): Promise<T> {
  if (isMarked(key)) throw new SessionFinalizedError();
  return enqueue(key, async () => {
    if (isMarked(key)) throw new SessionFinalizedError();
    return operation();
  });
}

export async function assertSessionOpen(key: string): Promise<void> {
  await withOpenSession(key, async () => undefined);
}

/**
 * Fence a cookie key before draining earlier work, then run its final cleanup.
 * A closed key remains fenced for the Docker/Instance 15-minute retry horizon.
 * If the bounded marker store cannot safely admit another close, finalization
 * fails rather than reviving a key inside that horizon.
 */
export async function finalizeSession<T>(
  key: string,
  operation: () => Promise<T>
): Promise<T> {
  pruneExpiredMarkers();
  const existing = markers.get(key);
  if (existing?.phase === "closing") return existing.pending as Promise<T>;
  if (existing?.phase === "closed") return Promise.resolve(existing.result as T);
  if (!existing && markers.size >= SESSION_FINALIZATION_MARKER_CAPACITY) {
    throw new SessionLifecycleCapacityError();
  }
  const marker: Marker = { phase: "closing" };
  markers.set(key, marker);
  const pending = enqueue(key, operation);
  marker.pending = pending;
  void pending.then(
    (result) => {
      rememberClosed(key, result);
    },
    () => {
      // Failed cleanup remains fenced until a matching finalization retries it.
      markers.set(key, { phase: "failed" });
    }
  );
  return pending;
}

export function isSessionFinalized(error: unknown): error is SessionFinalizedError {
  return error instanceof SessionFinalizedError;
}

export function isSessionLifecycleCapacityError(
  error: unknown
): error is SessionLifecycleCapacityError {
  return error instanceof SessionLifecycleCapacityError;
}

export function clearSessionLifecycleForTests(): void {
  markers.clear();
  queues.clear();
  nowForTests = undefined;
}

export function setSessionLifecycleNowForTests(clock: () => number): void {
  nowForTests = clock;
}
