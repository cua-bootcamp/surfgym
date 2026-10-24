import { File as NodeFile } from "node:buffer";
import { afterEach, describe, expect, it } from "vitest";

import { fileStore } from "./file-store";
import { createStateStore } from "./state-store";
import { MemoryStorage } from "./storage/memory-storage";
import type { UserState } from "./types";

type Data = Record<string, unknown>;

const ownedUserIds: string[] = [];

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function ownedUserId(label: string): string {
  const userId = `h7-state-file-${label}-${crypto.randomUUID()}`;
  ownedUserIds.push(userId);
  return userId;
}

async function cleanup(storage: MemoryStorage<Data>): Promise<void> {
  await Promise.all(
    ownedUserIds.splice(0).map(async (userId) => {
      await fileStore.deleteUserFiles(userId);
      await storage.delete(userId);
    }),
  );
}

class PausingMemoryStorage extends MemoryStorage<Data> {
  private pauseNextWrite = false;
  private writePaused = deferred();
  private releaseWrite = deferred();

  pauseOneWrite(): void {
    this.pauseNextWrite = true;
  }

  async waitForPausedWrite(): Promise<void> {
    await this.writePaused.promise;
  }

  resumeWrite(): void {
    this.releaseWrite.resolve();
  }

  override async set(userId: string, state: UserState<Data>): Promise<void> {
    if (this.pauseNextWrite) {
      this.pauseNextWrite = false;
      this.writePaused.resolve();
      await this.releaseWrite.promise;
    }
    await super.set(userId, state);
  }
}

function delayedFile(name: string, bytes: Uint8Array, entered: ReturnType<typeof deferred>, release: ReturnType<typeof deferred>): File {
  return {
    name,
    type: "text/plain",
    async arrayBuffer(): Promise<ArrayBuffer> {
      entered.resolve();
      await release.promise;
      return new Uint8Array(bytes).buffer;
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

describe("H7 state and file reset boundaries", () => {
  const storage = new MemoryStorage<Data>();

  afterEach(async () => {
    await cleanup(storage);
  });

  it("does not restore a stale derived patch after reset", async () => {
    const pausedStorage = new PausingMemoryStorage();
    const store = createStateStore(pausedStorage);
    const userId = ownedUserId("derived-reset");
    await store.replaceState(userId, { data: { profile: { locale: "en-US" } } });

    pausedStorage.pauseOneWrite();
    const derivedPatch = store.patchState(userId, { profile: { locale: "ko-KR" } });
    await pausedStorage.waitForPausedWrite();
    const reset = store.resetState(userId);
    pausedStorage.resumeWrite();
    await derivedPatch;
    const resetState = await reset;

    await expect(store.getState(userId)).resolves.toEqual(resetState);
  });

  it("does not retain a file whose write began before the same user reset", async () => {
    const store = createStateStore(storage);
    const userId = ownedUserId("stale-file");
    await store.replaceState(userId, { data: { marker: "before-reset" } });
    const writeStarted = deferred();
    const releaseWrite = deferred();
    const pendingUpload = fileStore.saveUpload(
      delayedFile("late.txt", new TextEncoder().encode("late"), writeStarted, releaseWrite),
      userId,
    );

    await writeStarted.promise;
    const deleteFiles = fileStore.deleteUserFiles(userId);
    releaseWrite.resolve();
    await pendingUpload;
    await deleteFiles;
    await store.resetState(userId);

    await expect(fileStore.listFiles(userId)).resolves.toEqual([]);
    await expect(store.getState(userId)).resolves.toMatchObject({ data: { uploads: [] } });
  });

  it("keeps repeated owned users isolated across actual files and state resets", async () => {
    const store = createStateStore(storage);
    const userIds = Array.from({ length: 16 }, (_, index) => ownedUserId(`retention-${index}`));

    await Promise.all(
      userIds.map(async (userId, index) => {
        await store.replaceState(userId, { data: { marker: `state-${index}` } });
        await fileStore.saveUpload(
          browserFile(`file-${index}`, `note-${index}.txt`),
          userId,
        );
      }),
    );
    expect(await storage.keys()).toEqual(expect.arrayContaining(userIds));
    expect((await Promise.all(userIds.map((userId) => fileStore.listFiles(userId)))).flat()).toHaveLength(16);

    await Promise.all(
      userIds.filter((_, index) => index % 2 === 0).map(async (userId) => {
        await fileStore.deleteUserFiles(userId);
        await store.resetState(userId);
      }),
    );

    for (const [index, userId] of userIds.entries()) {
      const state = await store.getState(userId);
      const files = await fileStore.listFiles(userId);
      if (index % 2 === 0) {
        expect(state.data.marker).toBeUndefined();
        expect(files).toEqual([]);
      } else {
        expect(state.data.marker).toBe(`state-${index}`);
        expect(files).toHaveLength(1);
        expect(files[0]?.name).toBe(`note-${index}.txt`);
      }
    }
  });
});
