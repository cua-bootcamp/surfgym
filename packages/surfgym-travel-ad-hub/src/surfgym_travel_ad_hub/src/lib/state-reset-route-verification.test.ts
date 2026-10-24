import { File as NodeFile } from "node:buffer";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { NextRequest } from "next/server";

type RouteModules = {
  DELETE: (request: NextRequest) => Promise<Response>;
  stateStore: {
    replaceState: (userId: string, state: { data: Record<string, unknown> }) => Promise<unknown>;
    getState: (userId: string) => Promise<{ data: Record<string, unknown> }>;
    deleteState: (userId: string) => Promise<void>;
  };
  fileStore: {
    saveUpload: (file: File, userId: string) => Promise<unknown>;
    listFiles: (userId: string) => Promise<unknown[]>;
    deleteUserFiles: (userId: string) => Promise<void>;
  };
};

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function delayedFile(
  entered: ReturnType<typeof deferred>,
  release: ReturnType<typeof deferred>,
): File {
  return {
    name: "late.txt",
    type: "text/plain",
    async arrayBuffer(): Promise<ArrayBuffer> {
      entered.resolve();
      await release.promise;
      return new TextEncoder().encode("late").buffer;
    },
  } as File;
}

function browserFile(contents: string, name: string): File {
  const file = new NodeFile([contents], name, { type: "text/plain" });
  return {
    name: file.name,
    lastModified: file.lastModified,
    webkitRelativePath: "",
    size: file.size,
    type: file.type,
    arrayBuffer: () => file.arrayBuffer(),
    bytes: async () => new Uint8Array(await file.arrayBuffer()),
    slice: () => { throw new Error("not used by upload fixture"); },
    stream: () => { throw new Error("not used by upload fixture"); },
    text: () => { throw new Error("not used by upload fixture"); },
  };
}

describe.sequential("H7 /api/state DELETE reset boundary", () => {
  const ownedUsers: Array<{ userId: string; modules: RouteModules }> = [];
  const ownedDirs: string[] = [];
  let cwdSpy: ReturnType<typeof vi.spyOn> | undefined;

  async function freshRoute(): Promise<RouteModules> {
    const runDir = await mkdtemp(path.join(tmpdir(), "surfgym-state-route-"));
    ownedDirs.push(runDir);
    // Vitest workers cannot chdir.  The production file store snapshots cwd at
    // module evaluation, so this gives it an owned upload root before import.
    cwdSpy = vi.spyOn(process, "cwd").mockReturnValue(runDir);
    vi.resetModules();
    const [{ DELETE }, { stateStore }, { fileStore }] = await Promise.all([
      import("../app/api/state/route"),
      import("./state-store"),
      import("./file-store"),
    ]);
    return { DELETE, stateStore, fileStore };
  }

  function requestFor(userId: string): NextRequest {
    // The documented query override avoids ambient next/headers cookie state.
    return new NextRequest(`http://route.test/api/state?cookie=${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
  }

  afterEach(async () => {
    for (const { userId, modules } of ownedUsers.splice(0)) {
      await modules.fileStore.deleteUserFiles(userId);
      await modules.stateStore.deleteState(userId);
    }
    cwdSpy?.mockRestore();
    cwdSpy = undefined;
    await Promise.all(ownedDirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })));
    vi.resetModules();
  });

  it("returns the owned cookie and clears pre-existing owned state and files", async () => {
    const modules = await freshRoute();
    const userId = `h7-route-control-${crypto.randomUUID()}`;
    ownedUsers.push({ userId, modules });
    await modules.stateStore.replaceState(userId, { data: { marker: "before-reset" } });
    await modules.fileStore.saveUpload(browserFile("before", "before.txt"), userId);

    const response = await modules.DELETE(requestFor(userId));

    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain(`user_id=${userId}`);
    await expect(modules.stateStore.getState(userId)).resolves.toMatchObject({ data: { uploads: [] } });
    await expect(modules.fileStore.listFiles(userId)).resolves.toEqual([]);
  });

  it("does not report reset complete while an earlier owned upload can repopulate files", async () => {
    const modules = await freshRoute();
    const userId = `h7-route-inflight-${crypto.randomUUID()}`;
    ownedUsers.push({ userId, modules });
    await modules.stateStore.replaceState(userId, { data: { marker: "before-reset" } });
    const entered = deferred();
    const release = deferred();
    const pendingUpload = modules.fileStore.saveUpload(delayedFile(entered, release), userId);

    await entered.promise;
    const response = modules.DELETE(requestFor(userId));
    release.resolve();
    await pendingUpload;

    expect((await response).status).toBe(200);
    await expect(modules.fileStore.listFiles(userId)).resolves.toEqual([]);
    await expect(modules.stateStore.getState(userId)).resolves.toMatchObject({ data: { uploads: [] } });
  });
});
