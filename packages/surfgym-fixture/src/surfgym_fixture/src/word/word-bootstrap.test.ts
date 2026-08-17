import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const registerPlugin = vi.fn();
  const createUniverDoc = vi.fn(() => ({ doc: { id: "fixture-document" } }));

  return {
    registerPlugin,
    createUniverDoc,
    newAPI: vi.fn(() => ({ createUniverDoc })),
    docsCorePreset: vi.fn(() => ({
      plugins: [[class DocsPlugin {}, { footer: true }]],
    })),
  };
});

vi.mock("@univerjs/core", () => ({
  LocaleType: { EN_US: "en-US" },
  mergeLocales: vi.fn((...locales: unknown[]) => ({ locales })),
  Univer: class {
    registerPlugin = mocks.registerPlugin;
  },
}));

vi.mock("@univerjs/core/facade", () => ({
  FUniver: { newAPI: mocks.newAPI },
}));

vi.mock("@univerjs/preset-docs-core", () => ({
  UniverDocsCorePreset: mocks.docsCorePreset,
}));

vi.mock("@univerjs/preset-docs-core/locales/en-US", () => ({ default: { locale: "en-US" } }));

import { createWordFixtureRuntime } from "./word-bootstrap";

describe("Word direct-OSS bootstrap", () => {
  it("registers the existing docs-core preset without the broad preset bundle and returns a usable document facade", () => {
    const runtime = createWordFixtureRuntime();

    expect(mocks.docsCorePreset).toHaveBeenCalledWith({
      container: "app",
      header: false,
      toolbar: false,
      footer: true,
      contextMenu: true,
    });
    expect(mocks.registerPlugin).toHaveBeenCalledTimes(1);
    expect(mocks.newAPI).toHaveBeenCalledTimes(1);
    expect(mocks.createUniverDoc).toHaveBeenCalledWith({});
    expect(runtime.document).toEqual({ doc: { id: "fixture-document" } });
  });
});
