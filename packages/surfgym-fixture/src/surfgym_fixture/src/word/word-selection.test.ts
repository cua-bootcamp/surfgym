import { describe, expect, it, vi } from "vitest";
import { createParagraphSelectionTracker, setSelectedParagraphLineSpacing } from "./word-selection";

const threeParagraphSnapshot = {
  body: {
    paragraphs: [
      { startIndex: 5 },
      { startIndex: 10 },
      { startIndex: 21 },
    ],
  },
};

describe("paragraph selection tracking", () => {
  it("maps the public selected text range to the selected paragraph", () => {
    let listener: ((event: unknown) => void) | undefined;
    const onCommandExecuted = vi.fn((nextListener: (event: unknown) => void) => {
      listener = nextListener;
    });
    const tracker = createParagraphSelectionTracker({ onCommandExecuted });

    listener?.({
      id: "doc.operation.set-selections",
      params: { ranges: [{ startOffset: 7, endOffset: 7, isActive: true }] },
    });

    expect(onCommandExecuted).toHaveBeenCalledOnce();
    expect(tracker.getSelectedParagraphIndexes(threeParagraphSnapshot)).toEqual([1]);

    const setAtom = vi.fn();
    setSelectedParagraphLineSpacing(tracker, threeParagraphSnapshot, 2, setAtom);
    expect(setAtom).toHaveBeenCalledWith(
      { kind: "paragraph", index: 1, property: "lineSpacing" },
      2,
    );
  });

  it("updates every paragraph covered by a non-collapsed selection and ignores other commands", () => {
    let listener: ((event: unknown) => void) | undefined;
    const tracker = createParagraphSelectionTracker({
      onCommandExecuted: (nextListener) => {
        listener = nextListener;
      },
    });

    listener?.({ id: "doc.command.set-inline-format-fontsize", params: { value: 12 } });
    expect(tracker.getSelectedParagraphIndexes(threeParagraphSnapshot)).toEqual([0]);

    listener?.({
      id: "doc.operation.set-selections",
      params: { ranges: [{ startOffset: 6, endOffset: 17, isActive: true }] },
    });

    expect(tracker.getSelectedParagraphIndexes(threeParagraphSnapshot)).toEqual([1, 2]);
  });
});
