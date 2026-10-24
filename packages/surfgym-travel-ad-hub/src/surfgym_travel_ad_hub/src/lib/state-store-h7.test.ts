import { afterEach, describe, expect, it } from "vitest";

import { createStateStore } from "./state-store";
import { MemoryStorage } from "./storage/memory-storage";
import type { UserState } from "./types";

type H7Data = Record<string, unknown>;

const ownedUserIds: string[] = [];

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function ownedUserId(label: string): string {
  const id = `h7-verification-${label}-${crypto.randomUUID()}`;
  ownedUserIds.push(id);
  return id;
}

async function removeOwnedStates(storage: MemoryStorage<H7Data>): Promise<void> {
  await Promise.all(ownedUserIds.splice(0).map((userId) => storage.delete(userId)));
}

class PausingMemoryStorage extends MemoryStorage<H7Data> {
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

  override async set(userId: string, state: UserState<H7Data>): Promise<void> {
    if (this.pauseNextWrite) {
      this.pauseNextWrite = false;
      this.writePaused.resolve();
      await this.releaseWrite.promise;
    }
    await super.set(userId, state);
  }
}

describe("H7 TravelHub state-store contracts", () => {
  afterEach(async () => {
    await removeOwnedStates(new MemoryStorage<H7Data>());
  });

  it("creates and persists a default state when an owned user has no stored state", async () => {
    const storage = new MemoryStorage<H7Data>();
    const store = createStateStore(storage);
    const userId = ownedUserId("missing");

    expect(await store.hasState(userId)).toBe(false);
    const state = await store.getState(userId);

    expect(state.meta.version).toBe(1);
    expect(await store.hasState(userId)).toBe(true);
    expect(await storage.get(userId)).toEqual(state);
  });

  it("retains both disjoint concurrent patches for one owned user", async () => {
    const storage = new MemoryStorage<H7Data>();
    const store = createStateStore(storage);
    const userId = ownedUserId("concurrent");
    await store.replaceState(userId, { data: { profile: {}, itinerary: {} } });

    await Promise.all([
      store.patchState(userId, { profile: { locale: "ko-KR" } }),
      store.patchState(userId, { itinerary: { trip: "Seoul" } }),
    ]);

    await expect(store.getState(userId)).resolves.toMatchObject({
      data: {
        profile: { locale: "ko-KR" },
        itinerary: { trip: "Seoul" },
      },
    });
  });

  it("does not let a paused patch overwrite a later reset", async () => {
    const storage = new PausingMemoryStorage();
    const store = createStateStore(storage);
    const userId = ownedUserId("reset-order");
    await store.replaceState(userId, { data: { profile: { locale: "en-US" } } });

    storage.pauseOneWrite();
    const patch = store.patchState(userId, { profile: { locale: "ko-KR" } });
    await storage.waitForPausedWrite();
    const reset = store.resetState(userId);
    storage.resumeWrite();
    await patch;
    const resetState = await reset;

    await expect(store.getState(userId)).resolves.toEqual(resetState);
  });

  it("returns and re-reads a JSON special key as an own data property", async () => {
    const storage = new MemoryStorage<H7Data>();
    const store = createStateStore(storage);
    const userId = ownedUserId("special-key");
    const patch = JSON.parse('{"__proto__":{"trip":"Seoul"}}') as Record<string, unknown>;

    const returned = await store.patchState(userId, patch);
    const reread = await store.getState(userId);

    expect(Object.hasOwn(returned.data, "__proto__")).toBe(true);
    expect(Object.hasOwn(reread.data, "__proto__")).toBe(true);
    expect((returned.data.__proto__ as { trip: string }).trip).toBe("Seoul");
    expect((reread.data.__proto__ as { trip: string }).trip).toBe("Seoul");
  });

  it("resets 20 owned users without crossing their state boundaries", async () => {
    const storage = new MemoryStorage<H7Data>();
    const store = createStateStore(storage);
    const userIds = Array.from({ length: 20 }, (_, index) => ownedUserId(`isolation-${index}`));

    await Promise.all(
      userIds.map((userId, index) =>
        store.replaceState(userId, { data: { marker: `owned-${index}` } }),
      ),
    );
    await Promise.all(userIds.filter((_, index) => index % 2 === 0).map((userId) => store.resetState(userId)));

    const states = await Promise.all(userIds.map((userId) => store.getState(userId)));
    for (const [index, state] of states.entries()) {
      if (index % 2 === 0) {
        expect(state.data.marker).toBeUndefined();
      } else {
        expect(state.data.marker).toBe(`owned-${index}`);
      }
    }
    expect(await storage.keys()).toEqual(expect.arrayContaining(userIds));
  });
});
