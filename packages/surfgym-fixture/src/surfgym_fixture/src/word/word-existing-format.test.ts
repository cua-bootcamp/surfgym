import { afterEach, describe, expect, it, vi } from "vitest";
import { get, set } from "./external";
import { WordRuntimeStore } from "./internal";
import { renderWordMockToolbar } from "./word-ui";

type RuntimeStoreInternals = {
  _runtime: unknown;
};

const runtimeStoreInternals = WordRuntimeStore as unknown as RuntimeStoreInternals;
let restoreWordRuntime: (() => void) | undefined;

function spacingSnapshot(): Record<string, unknown> {
  return {
    id: "word-existing-format-test",
    documentStyle: {},
    body: {
      dataStream: "Intro\rBody\rConclusion\r\n",
      textRuns: [{ st: 0, ed: 21, ts: { fs: 10 } }],
      paragraphs: [
        { startIndex: 5, paragraphStyle: { lineSpacing: 1 } },
        { startIndex: 10, paragraphStyle: { lineSpacing: 1 } },
        { startIndex: 21, paragraphStyle: { lineSpacing: 1 } },
      ],
    },
  };
}

function installWordRuntime(initialSnapshot: Record<string, unknown>) {
  const previousRuntime = runtimeStoreInternals._runtime;
  let snapshot = structuredClone(initialSnapshot);
  const document = {
    getSnapshot: () => structuredClone(snapshot),
    reset: (nextSnapshot: Record<string, unknown>) => {
      snapshot = structuredClone(nextSnapshot);
    },
  };

  WordRuntimeStore.runtime = {
    univer: {},
    univerAPI: {},
    document: { doc: document },
  } as never;

  return () => {
    runtimeStoreInternals._runtime = previousRuntime;
  };
}

afterEach(() => {
  document.body.innerHTML = "";
  restoreWordRuntime?.();
  restoreWordRuntime = undefined;
});

describe("existing Word line spacing and 12pt state", () => {
  it("characterizes the three-paragraph line-spacing and uniform-font atoms", () => {
    restoreWordRuntime = installWordRuntime(spacingSnapshot());

    expect(get({ kind: "paragraph", index: 0, property: "lineSpacing" })).toBe(1);
    expect(get({ kind: "paragraph", index: 1, property: "lineSpacing" })).toBe(1);
    expect(get({ kind: "paragraph", index: 2, property: "lineSpacing" })).toBe(1);
    expect(get({ kind: "document", property: "fontSizeOnly" })).toBe(10);

    set({ kind: "paragraph", index: 0, property: "lineSpacing" }, 1);
    set({ kind: "paragraph", index: 1, property: "lineSpacing" }, 2);
    set({ kind: "paragraph", index: 2, property: "lineSpacing" }, 1.5);
    set({ kind: "document", property: "fontSizeOnly" }, 12);

    expect(get({ kind: "paragraph", index: 0, property: "lineSpacing" })).toBe(1);
    expect(get({ kind: "paragraph", index: 1, property: "lineSpacing" })).toBe(2);
    expect(get({ kind: "paragraph", index: 2, property: "lineSpacing" })).toBe(1.5);
    expect(get({ kind: "document", property: "fontSizeOnly" })).toBe(12);
  });
});

describe("existing Word line spacing and font-size controls", () => {
  it("routes 12pt to the selection command and line spacing to its existing callback", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const executeCommand = vi.fn().mockResolvedValue(true);
    const setLineSpacing = vi.fn();

    renderWordMockToolbar({
      containerId: "toolbar",
      univerAPI: { executeCommand },
      getLineSpacing: () => 1,
      setLineSpacing,
    });

    const fontSize = document.querySelector<HTMLSelectElement>("[data-word-font-size]")!;
    fontSize.value = "12";
    fontSize.dispatchEvent(new Event("change", { bubbles: true }));
    expect(executeCommand).toHaveBeenCalledWith("doc.command.set-inline-format-fontsize", { value: 12 });

    document.querySelector<HTMLButtonElement>('[data-word-action="lineSpacing"]')!.click();
    document.querySelector<HTMLButtonElement>('[data-line-spacing-value="2"]')!.click();
    expect(setLineSpacing).toHaveBeenCalledWith(2);
  });
});
