import { afterEach, describe, expect, it, vi } from "vitest";
import { get, set } from "./external";
import {
  getTaskScopedWordPageNumberRequest,
  getTaskScopedWordReferenceHistory,
  getTaskScopedWordTabStopRequest,
  listTaskScopedWordReferences,
  recordTaskScopedWordCrossReference,
  recordTaskScopedWordImageRequest,
  recordTaskScopedWordPageNumberRequest,
  recordTaskScopedWordReference,
  recordTaskScopedWordTabStopRequest,
  resetTaskScopedWordInteractionRequests,
} from "./surfgym-word-interactions";
import {
  createParagraphSelectionTracker,
  recordCrossReferenceAtCurrentSelection,
  recordImageAtCurrentSelection,
  recordTabStopAtCurrentSelection,
} from "./word-selection";
import { renderWordMockToolbar } from "./word-ui";

afterEach(() => {
  resetTaskScopedWordInteractionRequests();
  document.body.innerHTML = "";
});

describe("Word page-number and tab-stop interaction records", () => {
  it("records only valid page-number Apply and exposes a read-only evaluator atom", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const recordPageNumberRequest = vi.fn(recordTaskScopedWordPageNumberRequest);
    renderWordMockToolbar({ containerId: "toolbar", recordPageNumberRequest });

    document.querySelector<HTMLButtonElement>('[data-word-action="pageNumber"]')!.click();
    expect(recordPageNumberRequest).not.toHaveBeenCalled();
    document.querySelector<HTMLButtonElement>('[data-word-page-number-cancel]')!.click();
    expect(getTaskScopedWordPageNumberRequest()).toBeNull();

    document.querySelector<HTMLButtonElement>('[data-word-action="pageNumber"]')!.click();
    document.querySelector<HTMLInputElement>('[data-word-page-number-start]')!.value = "0";
    document.querySelector<HTMLButtonElement>('[data-word-page-number-apply]')!.click();
    expect(recordPageNumberRequest).not.toHaveBeenCalled();

    document.querySelector<HTMLInputElement>('[data-word-page-number-start]')!.value = "3";
    document.querySelector<HTMLButtonElement>('[data-word-page-number-apply]')!.click();
    expect(get({ kind: "pageNumber", property: "request" })).toEqual({
      location: "footer", alignment: "left", applyTo: "all", startAt: 3,
    });
    expect(() => set({ kind: "pageNumber", property: "request" }, null)).toThrow("read-only");
  });

  it("captures the active range and paragraph indexes without mutating document content", () => {
    let listener: ((event: unknown) => void) | undefined;
    const tracker = createParagraphSelectionTracker({ onCommandExecuted: (next) => { listener = next; } });
    const snapshot = { body: { paragraphs: [{ startIndex: 5 }, { startIndex: 12 }] } };
    listener?.({
      id: "doc.operation.set-selections",
      params: { ranges: [{ startOffset: 7, endOffset: 10, isActive: true }] },
    });

    recordTabStopAtCurrentSelection(
      tracker,
      snapshot,
      { alignment: "end", offset: 6.5 },
      recordTaskScopedWordTabStopRequest,
    );

    expect(get({ kind: "tabStop", property: "request" })).toEqual({
      alignment: "end",
      offset: 6.5,
      paragraphIndexes: [1],
      range: { startOffset: 7, endOffset: 10 },
    });
    expect(() => set({ kind: "tabStop", property: "request" }, null)).toThrow("read-only");
  });

  it("does not record opening, cancellation, invalid offsets, or missing native selection", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const recordTabStopRequest = vi.fn();
    renderWordMockToolbar({ containerId: "toolbar", recordTabStopRequest });

    document.querySelector<HTMLButtonElement>('[data-word-action="tabStop"]')!.click();
    expect(recordTabStopRequest).not.toHaveBeenCalled();
    document.querySelector<HTMLButtonElement>('[data-word-tab-stop-cancel]')!.click();

    document.querySelector<HTMLButtonElement>('[data-word-action="tabStop"]')!.click();
    document.querySelector<HTMLInputElement>('[data-word-tab-stop-offset]')!.value = "-1";
    document.querySelector<HTMLButtonElement>('[data-word-tab-stop-apply]')!.click();
    expect(recordTabStopRequest).not.toHaveBeenCalled();

    const tracker = createParagraphSelectionTracker({ onCommandExecuted: () => undefined });
    expect(() => recordTabStopAtCurrentSelection(
      tracker,
      { body: { paragraphs: [{ startIndex: 5 }] } },
      { alignment: "right", offset: 4 },
      recordTaskScopedWordTabStopRequest,
    )).toThrow("active text selection");
    expect(getTaskScopedWordTabStopRequest()).toBeNull();
  });

  it("records an allowlisted inline image only from a collapsed native selection", () => {
    let listener: ((event: unknown) => void) | undefined;
    const tracker = createParagraphSelectionTracker({ onCommandExecuted: (next) => { listener = next; } });
    listener?.({ id: "doc.operation.set-selections", params: { ranges: [{ startOffset: 9, endOffset: 9, isActive: true }] } });

    recordImageAtCurrentSelection(
      tracker,
      { assetId: "1.png", width: 320, height: 180 },
      recordTaskScopedWordImageRequest,
    );
    expect(get({ kind: "image", property: "request" })).toEqual({
      assetId: "1.png", anchor: "inline", insertionOffset: 9, width: 320, height: 180,
    });
    expect(() => set({ kind: "image", property: "request" }, null)).toThrow("read-only");

    listener?.({ id: "doc.operation.set-selections", params: { ranges: [{ startOffset: 1, endOffset: 2, isActive: true }] } });
    expect(() => recordImageAtCurrentSelection(tracker, { assetId: "1.png" }, recordTaskScopedWordImageRequest))
      .toThrow("collapsed");
    expect(() => recordTaskScopedWordImageRequest({ assetId: "other.png", anchor: "inline", insertionOffset: 0 }))
      .toThrow("allowlisted");
  });

  it("records Add Reference before its linked numbered cross-reference", () => {
    let listener: ((event: unknown) => void) | undefined;
    const tracker = createParagraphSelectionTracker({ onCommandExecuted: (next) => { listener = next; } });
    const reference = recordTaskScopedWordReference("  Example citation.  ");
    listener?.({ id: "doc.operation.set-selections", params: { ranges: [{ startOffset: 20, endOffset: 30, isActive: true }] } });
    recordCrossReferenceAtCurrentSelection(
      tracker,
      { refId: reference.refId, display: "number" },
      recordTaskScopedWordCrossReference,
    );

    expect(listTaskScopedWordReferences()).toEqual([{ refId: "ref-1", citation: "Example citation." }]);
    expect(get({ kind: "reference", property: "history" })).toEqual([
      { sequence: 1, type: "addReference", refId: "ref-1", citation: "Example citation." },
      { sequence: 2, type: "insertCrossReference", refId: "ref-1", display: "number", range: { startOffset: 20, endOffset: 30 } },
    ]);
    expect(() => set({ kind: "reference", property: "history" }, null)).toThrow("read-only");
    expect(() => recordTaskScopedWordCrossReference({ refId: "missing", display: "number", range: { startOffset: 0, endOffset: 0 } }))
      .toThrow("recorded reference");
    expect(getTaskScopedWordReferenceHistory()).toHaveLength(2);
  });

  it("keeps image and reference dialogs side-effect free until valid final confirmation", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const recordImageRequest = vi.fn();
    const recordReferenceRequest = vi.fn(recordTaskScopedWordReference);
    const recordCrossReferenceRequest = vi.fn();
    renderWordMockToolbar({
      containerId: "toolbar",
      recordImageRequest,
      recordReferenceRequest,
      listRecordedReferences: listTaskScopedWordReferences,
      recordCrossReferenceRequest,
    });

    document.querySelector<HTMLButtonElement>('[data-word-action="image"]')!.click();
    expect(recordImageRequest).not.toHaveBeenCalled();
    document.querySelector<HTMLButtonElement>('[data-word-image-cancel]')!.click();
    document.querySelector<HTMLButtonElement>('[data-word-action="image"]')!.click();
    document.querySelector<HTMLInputElement>('[data-word-image-width]')!.value = "0";
    document.querySelector<HTMLButtonElement>('[data-word-image-insert]')!.click();
    expect(recordImageRequest).not.toHaveBeenCalled();
    document.querySelector<HTMLInputElement>('[data-word-image-width]')!.value = "200";
    document.querySelector<HTMLButtonElement>('[data-word-image-insert]')!.click();
    expect(recordImageRequest).toHaveBeenCalledWith({ assetId: "1.png", width: 200 });

    document.querySelector<HTMLButtonElement>('[data-word-action="addReference"]')!.click();
    document.querySelector<HTMLButtonElement>('[data-word-reference-cancel]')!.click();
    expect(recordReferenceRequest).not.toHaveBeenCalled();
    document.querySelector<HTMLButtonElement>('[data-word-action="addReference"]')!.click();
    document.querySelector<HTMLTextAreaElement>('[data-word-reference-citation]')!.value = "Citation";
    document.querySelector<HTMLButtonElement>('[data-word-reference-confirm]')!.click();
    expect(recordReferenceRequest).toHaveBeenCalledWith("Citation");

    document.querySelector<HTMLButtonElement>('[data-word-action="crossReference"]')!.click();
    expect(recordCrossReferenceRequest).not.toHaveBeenCalled();
    document.querySelector<HTMLButtonElement>('[data-word-cross-reference-insert]')!.click();
    expect(recordCrossReferenceRequest).toHaveBeenCalledWith({ refId: "ref-1", display: "number" });
  });
});
