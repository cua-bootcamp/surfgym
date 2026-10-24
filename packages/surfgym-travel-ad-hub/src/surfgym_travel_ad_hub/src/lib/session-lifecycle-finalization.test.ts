import { afterEach, describe, expect, it, vi } from "vitest";
import fs from "node:fs/promises";
import path from "node:path";
import { NextRequest } from "next/server";

import {
  clearSessionLifecycleForTests,
  finalizeSession,
  SESSION_FINALIZATION_MARKER_CAPACITY,
  SESSION_FINALIZATION_RETRY_HORIZON_MS,
  setSessionLifecycleNowForTests,
} from "./session-lifecycle";
import { createStateStore } from "./state-store";
import { MemoryStorage } from "./storage/memory-storage";
import type { UserState } from "./types";

type Data = Record<string, unknown>;

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

class PausingStorage extends MemoryStorage<Data> {
  entered = deferred();
  released = deferred();
  pause = true;

  override async set(userId: string, state: UserState<Data>): Promise<void> {
    if (this.pause) {
      this.pause = false;
      this.entered.resolve();
      await this.released.promise;
    }
    await super.set(userId, state);
  }
}

function request(
  userId: string,
  method: string,
  init: { body?: BodyInit | null; headers?: HeadersInit } = {}
): NextRequest {
  return new NextRequest(`http://127.0.0.1:3002/api/state?cookie=${encodeURIComponent(userId)}`, {
    method,
    ...init,
  });
}

describe.sequential("TravelHub explicit SurfGym finalization", () => {
  afterEach(() => {
    clearSessionLifecycleForTests();
  });

  it("marks closing before a queued state write drains, resets it, and fences later state access", async () => {
    const storage = new PausingStorage();
    const store = createStateStore(storage);
    const userId = `finalize-state-${crypto.randomUUID()}`;

    const pendingWrite = store.replaceState(userId, { data: { stale: true } });
    await storage.entered.promise;
    const finalization = finalizeSession(userId, () => store.resetStateForFinalization(userId));

    await expect(store.getState(userId)).rejects.toMatchObject({ name: "SessionFinalizedError" });
    storage.released.resolve();
    await pendingWrite;
    await finalization;

    await expect(store.patchState(userId, { late: true })).rejects.toMatchObject({ name: "SessionFinalizedError" });
    await expect(storage.get(userId)).resolves.toMatchObject({ data: { uploads: [] } });
  });

  it("does not permit reuse through the 15-minute retry horizon, then safely expires a closed marker", async () => {
    let clock = 1_000_000;
    setSessionLifecycleNowForTests(() => clock);
    const userId = `finalize-marker-${crypto.randomUUID()}`;

    await finalizeSession(userId, async () => "first");
    await expect(finalizeSession(userId, async () => "second")).resolves.toBe("first");

    clock += SESSION_FINALIZATION_RETRY_HORIZON_MS - 1;
    await expect(finalizeSession(userId, async () => "third")).resolves.toBe("first");

    clock += 1;
    await expect(finalizeSession(userId, async () => "after-expiry")).resolves.toBe("after-expiry");
  });

  it("joins duplicate closing requests, keeps cleanup failure fenced, and refuses unsafe marker eviction", async () => {
    let clock = 2_000_000;
    setSessionLifecycleNowForTests(() => clock);
    const userId = `finalize-retry-${crypto.randomUUID()}`;
    const gate = deferred();
    const first = finalizeSession(userId, async () => {
      await gate.promise;
      throw new Error("cleanup failed");
    });
    const joined = finalizeSession(userId, async () => undefined);
    gate.resolve();
    await expect(first).rejects.toThrow("cleanup failed");
    await expect(joined).rejects.toThrow("cleanup failed");
    await expect(finalizeSession(userId, async () => undefined)).resolves.toBeUndefined();

    await Promise.all(
      Array.from({ length: SESSION_FINALIZATION_MARKER_CAPACITY - 1 }, (_, index) =>
        finalizeSession(`finalize-capacity-${index}`, async () => undefined)
      )
    );
    await expect(finalizeSession("finalize-capacity-overflow", async () => undefined)).rejects.toMatchObject({
      name: "SessionLifecycleCapacityError",
    });
    await expect(finalizeSession(userId, async () => "replayed")).resolves.toBeUndefined();

    clock += SESSION_FINALIZATION_RETRY_HORIZON_MS;
    await expect(finalizeSession("finalize-capacity-after-expiry", async () => undefined)).resolves.toBeUndefined();
  });

  it("drains an already-started file write before final cleanup and rejects late file operations", async () => {
    const [{ fileStore }] = await Promise.all([import("./file-store")]);
    const userId = `finalize-file-${crypto.randomUUID()}`;
    const entered = deferred();
    const released = deferred();
    const file = {
      name: "late.txt",
      type: "text/plain",
      async arrayBuffer(): Promise<ArrayBuffer> {
        entered.resolve();
        await released.promise;
        return new TextEncoder().encode("late").buffer;
      },
    } as File;

    const pendingWrite = fileStore.saveUpload(file, userId);
    await entered.promise;
    const finalization = finalizeSession(userId, () => fileStore.deleteUserFilesForFinalization(userId));
    await expect(fileStore.listFiles(userId)).rejects.toMatchObject({ name: "SessionFinalizedError" });
    released.resolve();
    await pendingWrite;
    await finalization;

    await expect(fs.readdir(path.join(process.cwd(), "uploads", userId))).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("captures in-flight download bytes before final cleanup removes the file", async () => {
    const [{ fileStore }] = await Promise.all([import("./file-store")]);
    const userId = `finalize-download-${crypto.randomUUID()}`;
    const saved = await fileStore.saveUpload({
      name: "download.txt",
      type: "text/plain",
      async arrayBuffer(): Promise<ArrayBuffer> {
        return new TextEncoder().encode("captured-download").buffer;
      },
    } as File, userId);
    const entered = deferred();
    const released = deferred();
    const originalReadFile = fs.readFile;
    const readSpy = vi.spyOn(fs, "readFile").mockImplementation(
      (async (...args: Parameters<typeof fs.readFile>) => {
        entered.resolve();
        await released.promise;
        return originalReadFile(...args);
      }) as typeof fs.readFile
    );

    try {
      const download = fileStore.readFile(userId, saved.filename);
      await entered.promise;
      let cleanupFinished = false;
      const finalization = finalizeSession(userId, () => fileStore.deleteUserFilesForFinalization(userId))
        .finally(() => { cleanupFinished = true; });

      await Promise.resolve();
      expect(cleanupFinished).toBe(false);
      released.resolve();
      await expect(download).resolves.toEqual(Buffer.from("captured-download"));
      await finalization;
      await expect(fileStore.readFile(userId, saved.filename)).rejects.toMatchObject({ name: "SessionFinalizedError" });
    } finally {
      readSpy.mockRestore();
    }
  });

  it("returns 410 for late state, file list, and Task052 flow requests after the final reset", async () => {
    const [{ DELETE, GET, PUT, PATCH }, fileRoutes, fileDownload, task052Flow, adClosed, clickSession, openHotel, openCheckout] = await Promise.all([
      import("../app/api/state/route"),
      import("../app/api/files/route"),
      import("../app/api/files/[filename]/route"),
      import("../app/api/task052/flow/route"),
      import("../app/api/task052/ad-closed/route"),
      import("../app/api/task052/click-session/route"),
      import("../app/api/task052/open-hotel/route"),
      import("../app/api/task052/open-checkout/route"),
    ]);
    const userId = `finalize-route-${crypto.randomUUID()}`;

    const firstFinalization = await DELETE(
      request(userId, "DELETE", { headers: { "X-SurfGym-Finalize": "1" } })
    );
    expect(firstFinalization.status).toBe(200);
    await expect(firstFinalization.json()).resolves.toMatchObject({
      ok: true,
      cleanup_complete: true,
    });
    const replayedFinalization = await DELETE(
      request(userId, "DELETE", { headers: { "X-SurfGym-Finalize": "1" } })
    );
    expect(replayedFinalization.status).toBe(200);
    await expect(replayedFinalization.json()).resolves.toMatchObject({
      ok: true,
      cleanup_complete: true,
    });
    expect((await GET(request(userId, "GET"))).status).toBe(410);
    expect((await PUT(request(userId, "PUT", { body: JSON.stringify({ data: { late: true } }), headers: { "content-type": "application/json" } }))).status).toBe(410);
    expect((await PATCH(request(userId, "PATCH", { body: JSON.stringify({ data: { late: true } }), headers: { "content-type": "application/json" } }))).status).toBe(410);
    expect((await DELETE(request(userId, "DELETE"))).status).toBe(410);
    expect((await fileRoutes.GET(request(userId, "GET"))).status).toBe(410);
    const form = new FormData();
    form.append("files", new File(["late"], "late.txt", { type: "text/plain" }));
    expect((await fileRoutes.POST(request(userId, "POST", { body: form }))).status).toBe(410);
    expect((await fileDownload.GET(
      new NextRequest(`http://127.0.0.1:3002/api/files/late.txt?cookie=${encodeURIComponent(userId)}`),
      { params: Promise.resolve({ filename: "late.txt" }) }
    )).status).toBe(410);
    expect((await task052Flow.GET(request(userId, "GET"))).status).toBe(410);
    const action = (body: Record<string, unknown> = {}) => request(userId, "POST", {
      body: JSON.stringify(body),
      headers: { "content-type": "application/json", "x-task052-client": "1" },
    });
    expect((await adClosed.POST(action({ click_proof: {} }))).status).toBe(410);
    expect((await clickSession.POST(action({ public_key: "key", page_token: "token" }))).status).toBe(410);
    expect((await openHotel.POST(action({ hotel_id: "hotel-paris-1", click_proof: {} }))).status).toBe(410);
    expect((await openCheckout.POST(action({ hotel_id: "hotel-paris-1", room: "Deluxe Suite", click_proof: {} }))).status).toBe(410);
  });
});
