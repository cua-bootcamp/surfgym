import type { UserState, ReplaceStateInput, DefaultStateData } from "./types";
import { createDefaultState } from "./types";
import type { StateStorage } from "./storage/types";
import { getMemoryStorage } from "./storage/memory-storage";
import { withOpenSession } from "./session-lifecycle";

// Deep merge utility for PATCH operations
function deepMerge(
  dest: Record<string, unknown>,
  src: Record<string, unknown>
): Record<string, unknown> {
  const result = { ...dest };
  for (const key of Object.keys(src)) {
    const srcValue = src[key];
    const destValue = result[key];
    if (
      typeof destValue === "object" &&
      destValue !== null &&
      !Array.isArray(destValue) &&
      typeof srcValue === "object" &&
      srcValue !== null &&
      !Array.isArray(srcValue)
    ) {
      Object.defineProperty(result, key, {
        value: deepMerge(
          destValue as Record<string, unknown>,
          srcValue as Record<string, unknown>
        ),
        configurable: true,
        enumerable: true,
        writable: true,
      });
    } else {
      // Assignment to "__proto__" mutates an ordinary object's prototype;
      // PATCH must retain JSON keys as data instead.
      Object.defineProperty(result, key, {
        value: structuredClone(srcValue),
        configurable: true,
        enumerable: true,
        writable: true,
      });
    }
  }
  return result;
}

/**
 * State store factory that creates a store with the given storage backend.
 * Allows swapping storage implementations (memory, file, Redis, etc.)
 */
export function createStateStore<
  T extends Record<string, unknown> = DefaultStateData
>(storage: StateStorage<T>) {
  const transaction = {
    getState: getStateUnchecked,
    replaceState: replaceStateUnchecked,
    patchState: patchStateUnchecked,
  };
  return {
    /**
     * Get state for a user. Creates default state if none exists.
     */
    async getState(userId: string): Promise<UserState<T>> {
      return withOpenSession(userId, () => getStateUnchecked(userId));
    },

    /**
     * Replace entire state for a user.
     */
    async replaceState(
      userId: string,
      newState: ReplaceStateInput<Record<string, unknown>>
    ): Promise<UserState<T>> {
      return withOpenSession(userId, () => replaceStateUnchecked(userId, newState));
    },

    /**
     * Patch (deep merge) into existing state.
     */
    async patchState(
      userId: string,
      patch: Record<string, unknown>,
      note?: string | null
    ): Promise<UserState<T>> {
      return withOpenSession(userId, () => patchStateUnchecked(userId, patch, note));
    },

    /**
     * Reset state to defaults.
     */
    async resetState(userId: string): Promise<UserState<T>> {
      return withOpenSession(userId, () => resetStateUnchecked(userId));
    },

    /**
     * Delete state entirely.
     */
    async deleteState(userId: string): Promise<void> {
      await withOpenSession(userId, () => storage.delete(userId));
    },

    /**
     * Check if user has stored state.
     */
    async hasState(userId: string): Promise<boolean> {
      return withOpenSession(userId, () => storage.has(userId));
    },

    /**
     * Get the underlying storage adapter.
     */
    getStorage(): StateStorage<T> {
      return storage;
    },
    async resetStateForFinalization(userId: string): Promise<UserState<T>> {
      return resetStateUnchecked(userId);
    },
    async withTransaction<R>(
      userId: string,
      operation: (tx: typeof transaction) => Promise<R>
    ): Promise<R> {
      return withOpenSession(userId, () => operation(transaction));
    },
  };

  async function getStateUnchecked(userId: string): Promise<UserState<T>> {
    const state = await storage.get(userId);
    if (state) return state;
    const defaultState = createDefaultState() as UserState<T>;
    await storage.set(userId, defaultState);
    return defaultState;
  }

  async function replaceStateUnchecked(
    userId: string,
    newState: ReplaceStateInput<Record<string, unknown>>
  ): Promise<UserState<T>> {
    const now = new Date().toISOString();
    const state: UserState<T> = {
      meta: newState.meta
        ? {
            created_at: newState.meta.created_at || now,
            updated_at: now,
            version: newState.meta.version || 1,
            type: newState.meta.type || "unrestricted",
          }
        : { created_at: now, updated_at: now, version: 1, type: "unrestricted" },
      data: (newState.data || { uploads: [] }) as T,
      note: newState.note ?? null,
    };
    await storage.set(userId, state);
    return structuredClone(state);
  }

  async function patchStateUnchecked(
    userId: string,
    patch: Record<string, unknown>,
    note?: string | null
  ): Promise<UserState<T>> {
    const state = await getStateUnchecked(userId);
    const updatedState: UserState<T> = {
      meta: { ...state.meta, updated_at: new Date().toISOString(), version: state.meta.version + 1 },
      data: deepMerge(state.data as Record<string, unknown>, patch) as T,
      note: note !== undefined ? note : state.note,
    };
    await storage.set(userId, updatedState);
    return structuredClone(updatedState);
  }

  async function resetStateUnchecked(userId: string): Promise<UserState<T>> {
    const state = createDefaultState() as UserState<T>;
    await storage.set(userId, state);
    return structuredClone(state);
  }
}

export type StateStore<T extends Record<string, unknown> = DefaultStateData> =
  ReturnType<typeof createStateStore<T>>;

// Default store instance using memory storage
export const stateStore = createStateStore<DefaultStateData>(
  getMemoryStorage<DefaultStateData>()
);
