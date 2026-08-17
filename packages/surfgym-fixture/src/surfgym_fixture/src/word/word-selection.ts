type ParagraphSnapshot = {
  startIndex?: unknown;
};

type DocumentSnapshot = {
  body?: {
    paragraphs?: ParagraphSnapshot[];
  };
};

type SelectionRange = {
  startOffset?: unknown;
  endOffset?: unknown;
  isActive?: unknown;
};

type SelectionCommand = {
  id?: unknown;
  params?: {
    ranges?: unknown;
  };
};

type CommandEventSource = {
  onCommandExecuted: (listener: (event: unknown) => void) => void;
};

type ParagraphLineSpacingAtom = {
  kind: "paragraph";
  index: number;
  property: "lineSpacing";
};

function isSelectionCommand(event: unknown): event is SelectionCommand {
  return typeof event === "object" && event !== null;
}

function activeTextRange(event: SelectionCommand): { startOffset: number; endOffset: number } | undefined {
  if (event.id !== "doc.operation.set-selections" || !Array.isArray(event.params?.ranges)) {
    return undefined;
  }

  const range = event.params.ranges.find((candidate): candidate is SelectionRange =>
    typeof candidate === "object" && candidate !== null && (candidate as SelectionRange).isActive === true,
  ) ?? event.params.ranges.find((candidate): candidate is SelectionRange =>
    typeof candidate === "object" && candidate !== null,
  );

  if (!range || typeof range.startOffset !== "number" || typeof range.endOffset !== "number") {
    return undefined;
  }

  return {
    startOffset: Math.min(range.startOffset, range.endOffset),
    endOffset: Math.max(range.startOffset, range.endOffset),
  };
}

export function createParagraphSelectionTracker(commandEvents: CommandEventSource) {
  let selection: { startOffset: number; endOffset: number } | undefined;

  commandEvents.onCommandExecuted((event) => {
    if (!isSelectionCommand(event)) {
      return;
    }

    const nextSelection = activeTextRange(event);
    if (nextSelection) {
      selection = nextSelection;
    }
  });

  return {
    getSelectedParagraphIndexes(snapshot: DocumentSnapshot): number[] {
      const paragraphs = snapshot.body?.paragraphs ?? [];
      const paragraphEnds = paragraphs.map((paragraph) => paragraph.startIndex).filter(
        (startIndex): startIndex is number => typeof startIndex === "number",
      );
      if (paragraphEnds.length === 0) {
        return [0];
      }

      const activeSelection = selection ?? { startOffset: 0, endOffset: 0 };
      const indexes = paragraphEnds.flatMap((endOffset, index) => {
        const previousEndOffset = index === 0 ? -1 : (paragraphEnds[index - 1] ?? -1);
        return activeSelection.endOffset > previousEndOffset && activeSelection.startOffset <= endOffset
          ? [index]
          : [];
      });

      return indexes.length > 0 ? indexes : [Math.max(0, paragraphEnds.length - 1)];
    },
  };
}

export function setSelectedParagraphLineSpacing(
  tracker: ReturnType<typeof createParagraphSelectionTracker>,
  snapshot: DocumentSnapshot,
  lineSpacing: number,
  setAtom: (atom: ParagraphLineSpacingAtom, value: number) => void,
) {
  for (const index of tracker.getSelectedParagraphIndexes(snapshot)) {
    setAtom({ kind: "paragraph", index, property: "lineSpacing" }, lineSpacing);
  }
}
