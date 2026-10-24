import { File as NodeFile } from "node:buffer";
import { webcrypto } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import {
  clearSessionLifecycleForTests,
  finalizeSession,
} from "./session-lifecycle";
import { createTask052PageToken } from "./task052-click-sessions";
import {
  createTask052ClickProofMessage,
  TASK052_CLIENT_HEADER_NAME,
  TASK052_CLIENT_HEADER_VALUE,
  type Task052Action,
  type Task052ActionTarget,
  type Task052ClickProof,
} from "./task052-protocol";
import { patchTask052Flow } from "./task052-flow";
import { fileStore } from "./file-store";
import { stateStore } from "./state-store";

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

function request(
  userId: string,
  path: string,
  method: string,
  init: { body?: BodyInit | null; headers?: HeadersInit } = {},
): NextRequest {
  return new NextRequest(
    `http://127.0.0.1:3002${path}?cookie=${encodeURIComponent(userId)}`,
    { method, ...init },
  );
}

function routeFile(contents: string, name: string): File {
  const file = new NodeFile([contents], name, { type: "text/plain" });
  return {
    name: file.name,
    type: file.type,
    size: file.size,
    lastModified: file.lastModified,
    webkitRelativePath: "",
    arrayBuffer: () => file.arrayBuffer(),
    bytes: async () => new Uint8Array(await file.arrayBuffer()),
    slice: () => { throw new Error("not used by route fixture"); },
    stream: () => { throw new Error("not used by route fixture"); },
    text: () => { throw new Error("not used by route fixture"); },
  } as File;
}
function uploadRequest(userId: string, form: FormData): NextRequest {
  const routeRequest = request(userId, "/api/files", "POST");
  Object.defineProperty(routeRequest, "formData", {
    value: async () => form,
  });
  return routeRequest;
}
function taskHeaders(): Record<string, string> {
  return {
    "content-type": "application/json",
    [TASK052_CLIENT_HEADER_NAME]: TASK052_CLIENT_HEADER_VALUE,
  };
}

function base64Url(buffer: ArrayBuffer): string {
  return Buffer.from(buffer).toString("base64url");
}

async function proof(
  privateKey: CryptoKey,
  sessionId: string,
  challenge: string,
  action: Task052Action,
  target: Task052ActionTarget,
): Promise<Task052ClickProof> {
  const unsigned = {
    session_id: sessionId,
    challenge,
    action,
    target,
    signed_at: new Date().toISOString(),
  };
  const signature = await webcrypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    privateKey,
    new TextEncoder().encode(createTask052ClickProofMessage(unsigned)),
  );
  return { ...unsigned, signature: base64Url(signature) };
}

const ownedUsers: string[] = [];
function userId(label: string): string {
  const value = `task052-route-contract-${label}-${crypto.randomUUID()}`;
  ownedUsers.push(value);
  return value;
}

afterEach(async () => {
  vi.restoreAllMocks();
  clearSessionLifecycleForTests();
  await Promise.all(ownedUsers.splice(0).map(async (id) => {
    await fileStore.deleteUserFiles(id);
    await stateStore.getStorage().delete(id);
  }));
});

describe.sequential("Task052 lifecycle route contracts", () => {
  it("serializes an actual Task052 read-derive-write before finalization and leaves no resurrected flow", async () => {
    const id = userId("finalization");
    const entered = deferred();
    const release = deferred();
    const original = stateStore.withTransaction.bind(stateStore);
    let paused = false;

    vi.spyOn(stateStore, "withTransaction").mockImplementation((async (transactionUserId, operation) => {
      return original(transactionUserId, async (tx) => operation({
        ...tx,
        getState: async (readUserId: string) => {
          const state = await tx.getState(readUserId);
          if (!paused) {
            paused = true;
            entered.resolve();
            await release.promise;
          }
          return state;
        },
      }));
    }) as typeof stateStore.withTransaction);

    const pendingPatch = patchTask052Flow(id, { ad_closed: true }, "paused actual Task052 patch");
    await entered.promise;

    let finalizationSettled = false;
    const finalization = finalizeSession(id, () => stateStore.resetStateForFinalization(id))
      .finally(() => { finalizationSettled = true; });
    await Promise.resolve();
    expect(finalizationSettled).toBe(false);

    release.resolve();
    await expect(pendingPatch).resolves.toMatchObject({ ad_closed: true });
    await finalization;

    await expect(stateStore.getState(id)).rejects.toMatchObject({ name: "SessionFinalizedError" });
    const stored = await stateStore.getStorage().get(id);
    expect(stored).toMatchObject({ data: { uploads: [] } });
    expect(stored?.data.task052).toBeUndefined();
  });

  it("uses normal file and Task052 routes for upload/list/download, flow read, and three action transitions", async () => {
    const id = userId("normal-routes");
    const [files, fileDownload, flow, clickSession, adClosed, openHotel, openCheckout] = await Promise.all([
      import("../app/api/files/route"),
      import("../app/api/files/[filename]/route"),
      import("../app/api/task052/flow/route"),
      import("../app/api/task052/click-session/route"),
      import("../app/api/task052/ad-closed/route"),
      import("../app/api/task052/open-hotel/route"),
      import("../app/api/task052/open-checkout/route"),
    ]);

    const uploadForm = { getAll: (key: string) => key === "files" ? [routeFile("route-bytes", "route.txt")] : [] } as unknown as FormData;
    const upload = await files.POST(uploadRequest(id, uploadForm));
    expect(upload.status).toBe(200);
    const uploaded = await upload.json() as Array<{ filename: string }>;
    expect(uploaded).toHaveLength(1);
    const listed = await files.GET(request(id, "/api/files", "GET"));
    expect(listed.status).toBe(200);
    await expect(listed.json()).resolves.toEqual(expect.arrayContaining([expect.objectContaining({ filename: uploaded[0]!.filename })]));
    const downloaded = await fileDownload.GET(
      request(id, `/api/files/${encodeURIComponent(uploaded[0]!.filename)}`, "GET"),
      { params: Promise.resolve({ filename: uploaded[0]!.filename }) },
    );
    expect(downloaded.status).toBe(200);
    await expect(downloaded.text()).resolves.toBe("route-bytes");

    const initial = await flow.GET(request(id, "/api/task052/flow", "GET"));
    expect(initial.status).toBe(200);
    await expect(initial.json()).resolves.toMatchObject({ initialized: false, flow: { ad_closed: false } });

    const keyPair = await webcrypto.subtle.generateKey(
      { name: "ECDSA", namedCurve: "P-256" }, false, ["sign", "verify"],
    );
    const publicKey = await webcrypto.subtle.exportKey("jwk", keyPair.publicKey);
    const pageToken = await createTask052PageToken(id);
    const registered = await clickSession.POST(request(id, "/api/task052/click-session", "POST", {
      headers: taskHeaders(), body: JSON.stringify({ public_key: publicKey, page_token: pageToken }),
    }));
    expect(registered.status).toBe(200);
    const session = await registered.json() as { allowed: boolean; click_session_id: string; click_challenge: string };
    expect(session.allowed).toBe(true);

    const ad = await adClosed.POST(request(id, "/api/task052/ad-closed", "POST", {
      headers: taskHeaders(), body: JSON.stringify({ click_proof: await proof(keyPair.privateKey, session.click_session_id, session.click_challenge, "close_ad", {}) }),
    }));
    expect(ad.status).toBe(200);
    const adBody = await ad.json() as { allowed: boolean; next_click_challenge: string; flow: { ad_closed: boolean } };
    expect(adBody).toMatchObject({ allowed: true, flow: { ad_closed: true } });

    const hotel = await openHotel.POST(request(id, "/api/task052/open-hotel", "POST", {
      headers: taskHeaders(), body: JSON.stringify({ hotel_id: "hotel-paris-1", click_proof: await proof(keyPair.privateKey, session.click_session_id, adBody.next_click_challenge, "open_hotel", { hotel_id: "hotel-paris-1" }) }),
    }));
    expect(hotel.status).toBe(200);
    const hotelBody = await hotel.json() as { allowed: boolean; next_click_challenge: string; flow: { can_view_target_hotel: boolean } };
    expect(hotelBody).toMatchObject({ allowed: true, flow: { can_view_target_hotel: true } });

    const checkout = await openCheckout.POST(request(id, "/api/task052/open-checkout", "POST", {
      headers: taskHeaders(), body: JSON.stringify({ hotel_id: "hotel-paris-1", room: "Deluxe Suite", click_proof: await proof(keyPair.privateKey, session.click_session_id, hotelBody.next_click_challenge, "open_checkout", { hotel_id: "hotel-paris-1", room: "Deluxe Suite" }) }),
    }));
    expect(checkout.status).toBe(200);
    await expect(checkout.json()).resolves.toMatchObject({ allowed: true, flow: { can_view_checkout: true, checkout: { hotel_id: "hotel-paris-1", room: "Deluxe Suite" } } });

    const finalFlow = await flow.GET(request(id, "/api/task052/flow", "GET"));
    expect(finalFlow.status).toBe(200);
    await expect(finalFlow.json()).resolves.toMatchObject({ initialized: true, flow: { ad_closed: true, can_view_target_hotel: true, can_view_checkout: true } });
  });
});
