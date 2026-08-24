import { afterEach, describe, expect, it, vi } from "vitest";

import { get, installSurfGymBridge, set } from "./surfgym-bridge";

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

afterEach(() => {
  document.body.innerHTML = "";
  document.title = "";
  vi.unstubAllGlobals();
});
describe("SurfGym web bridge", () => {
  it("installs the stable window get/set surface", () => {
    const bridge = installSurfGymBridge();

    expect(window.surfgym).toBe(bridge);
    expect(window.surfgym.get).toBe(get);
    expect(window.surfgym.set).toBe(set);
  });

  it("reads page and element observations with the runtime evaluator semantics", async () => {
    document.title = "Travel Hub";
    document.body.innerHTML = '<input id="email" value="seed@example.com"><p id="status">Cancelled</p>';

    await expect(get({ target: "url" })).resolves.toBe(window.location.href);
    await expect(get({ target: "title" })).resolves.toBe("Travel Hub");
    await expect(get({ target: "text", selector: "#status" })).resolves.toBe("Cancelled");
    await expect(
      get({ target: "attr", selector: "#email", attr: "value" }),
    ).resolves.toBe("seed@example.com");
    await expect(get({ target: "text", selector: "#missing" })).resolves.toBeUndefined();
  });

  it("evaluates trusted synchronous and asynchronous seed scripts", async () => {
    await expect(get({ script: "document.title = 'Ready'; document.title" })).resolves.toBe("Ready");
    await expect(get({ script: "Promise.resolve(7)" })).resolves.toBe(7);
  });

  it("reads and patches api state paths", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ state: { data: { auth: { email: "seed@example.com" } } } }))
      .mockResolvedValueOnce(response({ state: { data: { auth: { email: "next@example.com" } } } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(get({ target: "api_state", path: "data.auth.email" })).resolves.toBe(
      "seed@example.com",
    );
    await set({ target: "api_state", path: ["data", "auth", "email"] }, "next@example.com");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/state", {
      method: "GET",
      headers: undefined,
      body: undefined,
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/state", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: { auth: { email: "next@example.com" } } }),
    });
  });

  it("accepts app_state as the backend-neutral state target", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ state: { data: { auth: { email: "seed@example.com" } } } }))
      .mockResolvedValueOnce(response({ state: { data: { auth: { email: "next@example.com" } } } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(get({ target: "app_state", path: "data.auth.email" })).resolves.toBe(
      "seed@example.com",
    );
    await set({ target: "app_state", path: ["data", "auth", "email"] }, "next@example.com");

    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/state", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: { auth: { email: "next@example.com" } } }),
    });
  });

  it("resets server state through the shared release sentinel", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ state: { data: {} } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(get({ $surfgym: { type: "release" } })).resolves.toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/state", {
      method: "DELETE",
      headers: undefined,
      body: undefined,
    });
  });

  it("rejects writes outside api state and failed state requests", async () => {
    await expect(set({ target: "url" }, "https://example.com")).rejects.toThrow(
      "Only app_state and legacy api_state web specs are settable.",
    );

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, 500)));
    await expect(get({ target: "api_state", path: "data" })).rejects.toThrow("HTTP 500");
  });
});
