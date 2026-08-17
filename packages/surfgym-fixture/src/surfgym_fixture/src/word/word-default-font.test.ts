import { afterEach, describe, expect, it, vi } from "vitest";
import { get, set } from "./external";
import { WordRuntimeStore } from "./internal";
import { renderWordMockToolbar } from "./word-ui";

type RuntimeStoreInternals = {
  _runtime: unknown;
};

type MutableDocument = {
  getSnapshot: () => Record<string, unknown>;
  reset: (snapshot: Record<string, unknown>) => void;
};

const runtimeStoreInternals = WordRuntimeStore as unknown as RuntimeStoreInternals;
let restoreWordRuntime: (() => void) | undefined;

const defaultFontSpec = {
  kind: "document" as const,
  property: "defaultFontFamily" as const,
};

function installWordRuntime(initialSnapshot: Record<string, unknown>) {
  const previousRuntime = runtimeStoreInternals._runtime;
  let snapshot = structuredClone(initialSnapshot);
  const document: MutableDocument = {
    getSnapshot: () => structuredClone(snapshot),
    reset: (nextSnapshot) => {
      snapshot = structuredClone(nextSnapshot);
    },
  };

  WordRuntimeStore.runtime = {
    univer: {},
    univerAPI: {},
    document: { doc: document },
  } as never;

  return {
    document,
    restore: () => {
      runtimeStoreInternals._runtime = previousRuntime;
    },
  };
}

function documentSnapshot(text = ""): Record<string, unknown> {
  return {
    id: "word-default-font-test",
    documentStyle: {},
    body: {
      dataStream: text ? `${text.replaceAll("\n", "\r")}\r\n` : "\r\n",
      textRuns: [],
      paragraphs: [],
    },
  };
}

afterEach(() => {
  document.body.innerHTML = "";
  restoreWordRuntime?.();
  restoreWordRuntime = undefined;
});

describe("Word document default font atom", () => {
  it("sets Times New Roman on an empty document through the canonical document atom", () => {
    const runtime = installWordRuntime(documentSnapshot());
    restoreWordRuntime = runtime.restore;

    set(defaultFontSpec, "Times New Roman");

    expect(get(defaultFontSpec)).toBe("Times New Roman");
    expect((runtime.document.getSnapshot().documentStyle as Record<string, unknown>).textStyle)
      .toEqual({ ff: "Times New Roman" });
  });

  it("uses the document default as the effective font of existing implicit text", () => {
    const runtime = installWordRuntime(documentSnapshot("Implicit text"));
    restoreWordRuntime = runtime.restore;

    set(defaultFontSpec, "Times New Roman");

    expect(get({ kind: "text", text: "Implicit text", property: "fontFamily" })).toBe("Times New Roman");
  });

  it("preserves an explicit Arial run while changing the document default", () => {
    const snapshot = documentSnapshot("Implicit\nExplicit");
    const body = snapshot.body as Record<string, unknown>;
    body.textRuns = [{ st: 9, ed: 17, ts: { ff: "Arial" } }];
    const runtime = installWordRuntime(snapshot);
    restoreWordRuntime = runtime.restore;

    set(defaultFontSpec, "Times New Roman");

    expect(get({ kind: "text", text: "Implicit", property: "fontFamily" })).toBe("Times New Roman");
    expect(get({ kind: "text", text: "Explicit", property: "fontFamily" })).toBe("Arial");
    expect(((runtime.document.getSnapshot().body as Record<string, unknown>).textRuns)).toEqual([
      { st: 9, ed: 17, ts: { ff: "Arial" } },
    ]);
  });

  it("uses the document default for new implicit text after a body reset", () => {
    const runtime = installWordRuntime(documentSnapshot());
    restoreWordRuntime = runtime.restore;

    set(defaultFontSpec, "Times New Roman");
    set({ kind: "body", property: "text" }, "New implicit text");

    expect(get({ kind: "text", text: "New implicit text", property: "fontFamily" })).toBe("Times New Roman");
  });

  it("round-trips the atom after a document reset and rejects blank font families without mutation", () => {
    const runtime = installWordRuntime(documentSnapshot("Body"));
    restoreWordRuntime = runtime.restore;

    set(defaultFontSpec, "Times New Roman");
    runtime.document.reset(documentSnapshot("Body"));
    expect(get(defaultFontSpec)).toBeUndefined();
    set(defaultFontSpec, "Times New Roman");
    expect(get(defaultFontSpec)).toBe("Times New Roman");
    expect(() => set(defaultFontSpec, "   ")).toThrow("defaultFontFamily");
    expect(() => set(defaultFontSpec, null)).toThrow("defaultFontFamily");
    expect(get(defaultFontSpec)).toBe("Times New Roman");
  });
});

describe("Word document default font UI", () => {
  it("keeps document default font separate from the selection font command", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const executeCommand = vi.fn().mockResolvedValue(true);
    const setDocumentDefaultFont = vi.fn();

    renderWordMockToolbar({
      containerId: "toolbar",
      univerAPI: { executeCommand },
      getDocumentDefaultFont: () => "Calibri",
      setDocumentDefaultFont,
    });

    const selectionFont = document.querySelector<HTMLSelectElement>("[data-word-font-family]")!;
    selectionFont.value = "Arial";
    selectionFont.dispatchEvent(new Event("change", { bubbles: true }));

    expect(executeCommand).toHaveBeenCalledWith("doc.command.set-inline-format-font-family", {
      value: "Arial",
    });
    expect(setDocumentDefaultFont).not.toHaveBeenCalled();

    const documentDefault = document.querySelector<HTMLSelectElement>("[data-word-document-default-font]")!;
    documentDefault.value = "Times New Roman";
    documentDefault.dispatchEvent(new Event("change", { bubbles: true }));

    expect(setDocumentDefaultFont).toHaveBeenCalledWith("Times New Roman");
    expect(executeCommand).toHaveBeenCalledTimes(1);
  });
});
