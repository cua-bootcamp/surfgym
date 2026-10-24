import { NextRequest } from "next/server";
import { createResponseWithCookie, getUserId } from "@/lib/cookies";
import { getTask052Flow } from "@/lib/task052-flow";
import { assertSessionOpen, isSessionFinalized } from "@/lib/session-lifecycle";

// GET /api/task052/flow - Retrieve task 052 flow state for this user.
export async function GET(request: NextRequest) {
  const userId = await getUserId(request);
  try {
    await assertSessionOpen(userId);
    const { flow, initialized } = await getTask052Flow(userId);

    return createResponseWithCookie({ flow, initialized }, userId);
  } catch (error) {
    if (isSessionFinalized(error)) {
      return createResponseWithCookie(
        { detail: "SurfGym session finalized" },
        userId,
        410
      );
    }
    throw error;
  }
}
