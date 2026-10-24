import { NextRequest } from "next/server";
import { getUserId, createResponseWithCookie } from "@/lib/cookies";
import { stateStore } from "@/lib/state-store";
import { fileStore } from "@/lib/file-store";
import { StateResponse, StateRequest, StatePatchRequest } from "@/lib/types";
import { getTask052FlowFromState } from "@/lib/task052-flow";
import {
  shouldMergeTask052Seed,
  validateTask052StatePatch,
  validateTask052StatePut,
} from "@/lib/task052-state-guard";
import {
  finalizeSession,
  isSessionLifecycleCapacityError,
  isSessionFinalized,
} from "@/lib/session-lifecycle";

function finalizedResponse(userId: string) {
  return createResponseWithCookie(
    { detail: "SurfGym session finalized" },
    userId,
    410
  );
}

// GET /api/state - Retrieve current user state
export async function GET(request: NextRequest) {
  const userId = await getUserId(request);
  try {
    const state = await stateStore.getState(userId);

    const response: StateResponse = {
      user_id: userId,
      state,
    };

    return createResponseWithCookie(response, userId);
  } catch (error) {
    if (isSessionFinalized(error)) return finalizedResponse(userId);
    throw error;
  }
}

// PUT /api/state - Replace entire state
export async function PUT(request: NextRequest) {
  const userId = await getUserId(request);

  let payload: StateRequest;
  try {
    payload = await request.json();
  } catch {
    return createResponseWithCookie(
      { detail: "Invalid JSON body" },
      userId,
      400
    );
  }

  try {
  const payloadData = payload.data || {};
  const task052Validation = validateTask052StatePut(payloadData);
  if (!task052Validation.ok) {
    return createResponseWithCookie(
      { detail: task052Validation.detail },
      userId,
      task052Validation.status
    );
  }

  const state = await stateStore.withTransaction(userId, async (tx) => {
    let data = payloadData;
    if (shouldMergeTask052Seed(payloadData)) {
      const retainedData: Record<string, unknown> = {
        ...(await tx.getState(userId)).data,
      };
      data = {
        ...retainedData,
        ...payloadData,
        task052_click_sessions: [],
        task052_page_tokens: [],
      };
    }

    const nextState: {
      data: Record<string, unknown>;
      note: string | null;
      meta?: StateRequest["meta"];
    } = { data, note: payload.note ?? null };
    if (payload.meta) nextState.meta = payload.meta;
    return tx.replaceState(userId, nextState);
  });

  const response: StateResponse = {
    user_id: userId,
    state,
  };

  return createResponseWithCookie(response, userId);
  } catch (error) {
    if (isSessionFinalized(error)) return finalizedResponse(userId);
    throw error;
  }
}

// PATCH /api/state - Merge into existing state
export async function PATCH(request: NextRequest) {
  const userId = await getUserId(request);

  let payload: StatePatchRequest;
  try {
    payload = await request.json();
  } catch {
    return createResponseWithCookie(
      { detail: "Invalid JSON body" },
      userId,
      400
    );
  }

  try {
  const payloadData = payload.data || {};
  const state = await stateStore.withTransaction(userId, async (tx) => {
    const { flow } = getTask052FlowFromState(await tx.getState(userId));
    const task052Validation = validateTask052StatePatch(payloadData, flow);
    if (!task052Validation.ok) {
      throw new Task052ValidationError(
        task052Validation.detail,
        task052Validation.status
      );
    }
    return tx.patchState(userId, payloadData, payload.note);
  });

  const response: StateResponse = {
    user_id: userId,
    state,
  };

  return createResponseWithCookie(response, userId);
  } catch (error) {
    if (error instanceof Task052ValidationError) {
      return createResponseWithCookie({ detail: error.detail }, userId, error.status);
    }
    if (isSessionFinalized(error)) return finalizedResponse(userId);
    throw error;
  }
}

// DELETE /api/state - Reset and clear state
export async function DELETE(request: NextRequest) {
  const userId = await getUserId(request);
  const finalizing = request.headers.get("X-SurfGym-Finalize") === "1";

  try {
    const state = finalizing
      ? await finalizeSession(userId, async () => {
          await fileStore.deleteUserFilesForFinalization(userId);
          return stateStore.resetStateForFinalization(userId);
        })
      : await resetOrdinarySession(userId);

    const response: StateResponse = {
      user_id: userId,
      state,
    };

    return createResponseWithCookie(
      finalizing ? { ...response, ok: true, cleanup_complete: true } : response,
      userId
    );
  } catch (error) {
    if (isSessionFinalized(error)) return finalizedResponse(userId);
    if (isSessionLifecycleCapacityError(error)) {
      return createResponseWithCookie(
        { detail: "SurfGym finalization capacity exhausted" },
        userId,
        503
      );
    }
    throw error;
  }
}

async function resetOrdinarySession(userId: string) {
  await fileStore.deleteUserFiles(userId);
  return stateStore.resetState(userId);
}

class Task052ValidationError extends Error {
  constructor(
    readonly detail: string,
    readonly status: number
  ) {
    super(detail);
  }
}
