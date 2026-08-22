import { afterEach, describe, expect, it, vi } from "vitest";
import { get } from "./external";
import { _insertBodyPageBreakAt, WordRuntimeStore } from "./internal";
import {
  createParagraphSelectionTracker,
  insertPageBreakAtCurrentSelection
} from "./word-selection";
import { renderWordMockToolbar } from "./word-ui";

type RuntimeStoreInternals = {
  _runtime: unknown;
};

const runtimeStoreInternals = WordRuntimeStore as unknown as RuntimeStoreInternals;
let restoreWordRuntime: (() => void) | undefined;

function formattedSnapshot(): Record<string, unknown> {
  return {
    id: "word-page-break-test",
    documentStyle: {},
    body: {
      dataStream: "Alpha\rBeta\r\n",
      textRuns: [
        { st: 0, ed: 5, ts: { bl: 1 } },
        { st: 6, ed: 10, ts: { it: 1, ff: "Arial" } }
      ],
      paragraphs: [
        { startIndex: 5, paragraphStyle: { lineSpacing: 1 } },
        { startIndex: 10, paragraphStyle: { lineSpacing: 2 } }
      ],
      sectionBreaks: [{ startIndex: 11, charSpace: 4 }],
      customRanges: [{ startIndex: 6, endIndex: 10, rangeId: "beta", rangeType: 5 }]
    }
  };
}

function installWordRuntime(initialSnapshot: Record<string, unknown>) {
  const previousRuntime = runtimeStoreInternals._runtime;
  let snapshot = structuredClone(initialSnapshot);
  const reset = vi.fn((nextSnapshot: Record<string, unknown>) => {
    snapshot = structuredClone(nextSnapshot);
  });
  const document = {
    getSnapshot: () => structuredClone(snapshot),
    reset
  };

  WordRuntimeStore.runtime = {
    univer: {},
    univerAPI: {},
    document: { doc: document }
  } as never;

  return {
    getSnapshot: () => structuredClone(snapshot),
    reset,
    restore: () => {
      runtimeStoreInternals._runtime = previousRuntime;
    }
  };
}

function selectionTracker(startOffset: number, endOffset = startOffset) {
  let listener: ((event: unknown) => void) | undefined;
  const tracker = createParagraphSelectionTracker({
    onCommandExecuted: (nextListener) => {
      listener = nextListener;
    }
  });
  listener?.({
    id: "doc.operation.set-selections",
    params: { ranges: [{ startOffset, endOffset, isActive: true }] }
  });
  return tracker;
}

afterEach(() => {
  document.body.innerHTML = "";
  restoreWordRuntime?.();
  restoreWordRuntime = undefined;
});

describe("Word page-break insertion", () => {
  it("inserts at the active caret while preserving runs and paragraph styles across reset and readback", () => {
    const runtime = installWordRuntime(formattedSnapshot());
    restoreWordRuntime = runtime.restore;

    insertPageBreakAtCurrentSelection(selectionTracker(6), _insertBodyPageBreakAt);

    expect(runtime.reset).toHaveBeenCalledOnce();
    expect(get({ kind: "body", property: "textWithPageBreak" })).toBe("Alpha\n\fBeta");
    expect(get({ kind: "text", text: "Alpha", property: "bold" })).toBe(true);
    expect(get({ kind: "text", text: "Beta", property: "italic" })).toBe(true);
    expect(get({ kind: "text", text: "Beta", property: "fontFamily" })).toBe("Arial");
    expect(get({ kind: "paragraph", index: 0, property: "lineSpacing" })).toBe(1);
    expect(get({ kind: "paragraph", index: 1, property: "lineSpacing" })).toBe(2);

    const snapshot = runtime.getSnapshot() as {
      body: {
        dataStream: string;
        textRuns: Array<Record<string, unknown>>;
        paragraphs: Array<Record<string, unknown>>;
        sectionBreaks: Array<Record<string, unknown>>;
        customRanges: Array<Record<string, unknown>>;
      };
    };
    expect(snapshot.body.dataStream).toBe("Alpha\r\nBeta\r\n");
    expect(snapshot.body.textRuns).toEqual([
      { st: 0, ed: 5, ts: { bl: 1 } },
      { st: 7, ed: 11, ts: { it: 1, ff: "Arial" } }
    ]);
    expect(snapshot.body.paragraphs).toEqual([
      { startIndex: 5, paragraphStyle: { lineSpacing: 1 } },
      { startIndex: 11, paragraphStyle: { lineSpacing: 2 } }
    ]);
    expect(snapshot.body.sectionBreaks).toEqual([
      { startIndex: 6, sectionType: 2 },
      { startIndex: 12, charSpace: 4 }
    ]);
    expect(snapshot.body.customRanges).toEqual([
      { startIndex: 7, endIndex: 11, rangeId: "beta", rangeType: 5 }
    ]);

    runtime.restore();
    const reloadedRuntime = installWordRuntime(snapshot as unknown as Record<string, unknown>);
    restoreWordRuntime = reloadedRuntime.restore;
    expect(get({ kind: "body", property: "textWithPageBreak" })).toBe("Alpha\n\fBeta");
    expect(get({ kind: "text", text: "Beta", property: "fontFamily" })).toBe("Arial");
    expect(get({ kind: "paragraph", index: 1, property: "lineSpacing" })).toBe(2);
  });

  it("fails explicitly for absent, non-collapsed, and out-of-body selections without resetting", () => {
    const runtime = installWordRuntime(formattedSnapshot());
    restoreWordRuntime = runtime.restore;
    const trackerWithoutSelection = createParagraphSelectionTracker({
      onCommandExecuted: () => {}
    });

    expect(() =>
      insertPageBreakAtCurrentSelection(trackerWithoutSelection, _insertBodyPageBreakAt)
    ).toThrow("without an active text selection");
    expect(() =>
      insertPageBreakAtCurrentSelection(selectionTracker(1, 3), _insertBodyPageBreakAt)
    ).toThrow("non-collapsed text selection");
    expect(() =>
      insertPageBreakAtCurrentSelection(selectionTracker(99), _insertBodyPageBreakAt)
    ).toThrow("outside the document body");
    expect(runtime.reset).not.toHaveBeenCalled();
  });

  it("exposes the insertion as an enabled toolbar action", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const insertPageBreak = vi.fn();

    renderWordMockToolbar({
      containerId: "toolbar",
      insertPageBreak
    });

    const button = document.querySelector<HTMLButtonElement>('[data-word-action="pageBreak"]')!;
    expect(button.getAttribute("aria-disabled")).toBe("false");
    expect(button.getAttribute("aria-label")).toBe("Insert Page Break");
    button.click();
    expect(insertPageBreak).toHaveBeenCalledOnce();
  });
});
