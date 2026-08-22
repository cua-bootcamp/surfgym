export type WordPageNumberRequest = {
  location: "footer";
  alignment: "left";
  applyTo: "all";
  startAt: number;
};

export type WordTabStopRequest = {
  alignment: "end" | "right";
  offset: number;
  paragraphIndexes: number[];
  range: { startOffset: number; endOffset: number };
};

export type WordImageRequest = {
  assetId: string;
  anchor: "inline";
  insertionOffset: number;
  width?: number;
  height?: number;
};

export type WordReferenceEvent =
  | { sequence: number; type: "addReference"; refId: string; citation: string }
  | {
    sequence: number;
    type: "insertCrossReference";
    refId: string;
    display: "number";
    range: { startOffset: number; endOffset: number };
  };

export const WORD_FIXTURE_TASK_ASSETS = [{ assetId: "1.png", label: "1.png" }] as const;

let pageNumberRequest: WordPageNumberRequest | null = null;
let tabStopRequest: WordTabStopRequest | null = null;
let imageRequest: WordImageRequest | null = null;
let referenceSequence = 1;
let referenceIdSequence = 1;
let referenceHistory: WordReferenceEvent[] = [];

export function recordTaskScopedWordPageNumberRequest(request: WordPageNumberRequest) {
  if (request.location !== "footer" || request.alignment !== "left" || request.applyTo !== "all") {
    throw new Error("Page number request must target every page at the bottom left.");
  }
  if (!Number.isInteger(request.startAt) || request.startAt <= 0) {
    throw new Error("Page number start must be a positive integer.");
  }
  pageNumberRequest = { ...request };
  return getTaskScopedWordPageNumberRequest();
}

export function recordTaskScopedWordTabStopRequest(request: WordTabStopRequest) {
  if (request.alignment !== "end" && request.alignment !== "right") {
    throw new Error("Tab stop alignment must be end or right.");
  }
  if (!Number.isFinite(request.offset) || request.offset <= 0) {
    throw new Error("Tab stop offset must be positive.");
  }
  if (!request.paragraphIndexes.length || request.paragraphIndexes.some((index) => !Number.isInteger(index) || index < 0)) {
    throw new Error("Tab stop request must include active paragraph indexes.");
  }
  if (!Number.isInteger(request.range.startOffset) || !Number.isInteger(request.range.endOffset) ||
    request.range.startOffset < 0 || request.range.endOffset < request.range.startOffset) {
    throw new Error("Tab stop request must include a valid active range.");
  }
  tabStopRequest = {
    ...request,
    paragraphIndexes: [...request.paragraphIndexes],
    range: { ...request.range },
  };
  return getTaskScopedWordTabStopRequest();
}

export function getTaskScopedWordPageNumberRequest() {
  return pageNumberRequest ? { ...pageNumberRequest } : null;
}

export function getTaskScopedWordTabStopRequest() {
  return tabStopRequest ? {
    ...tabStopRequest,
    paragraphIndexes: [...tabStopRequest.paragraphIndexes],
    range: { ...tabStopRequest.range },
  } : null;
}

export function recordTaskScopedWordImageRequest(request: WordImageRequest) {
  if (!WORD_FIXTURE_TASK_ASSETS.some((asset) => asset.assetId === request.assetId)) {
    throw new Error("Image asset is not allowlisted for this fixture task.");
  }
  if (request.anchor !== "inline" || !Number.isInteger(request.insertionOffset) || request.insertionOffset < 0) {
    throw new Error("Image request must use an inline anchor at a valid insertion offset.");
  }
  for (const [label, value] of [["width", request.width], ["height", request.height]] as const) {
    if (value !== undefined && (!Number.isFinite(value) || value <= 0)) {
      throw new Error(`Image ${label} must be positive when provided.`);
    }
  }
  imageRequest = { ...request };
  return getTaskScopedWordImageRequest();
}

export function getTaskScopedWordImageRequest() {
  return imageRequest ? { ...imageRequest } : null;
}

export function recordTaskScopedWordReference(citation: string) {
  const normalizedCitation = citation.trim();
  if (!normalizedCitation) throw new Error("Reference citation must not be empty.");
  const event: WordReferenceEvent = {
    sequence: referenceSequence++,
    type: "addReference",
    refId: `ref-${referenceIdSequence++}`,
    citation: normalizedCitation,
  };
  referenceHistory.push(event);
  return { ...event };
}

export function listTaskScopedWordReferences() {
  return referenceHistory
    .filter((event): event is Extract<WordReferenceEvent, { type: "addReference" }> => event.type === "addReference")
    .map((event) => ({ refId: event.refId, citation: event.citation }));
}

export function recordTaskScopedWordCrossReference(request: {
  refId: string;
  display: "number";
  range: { startOffset: number; endOffset: number };
}) {
  if (!listTaskScopedWordReferences().some((reference) => reference.refId === request.refId)) {
    throw new Error("Cross-reference must target a recorded reference.");
  }
  if (request.display !== "number") throw new Error("Cross-reference display must be number.");
  if (!Number.isInteger(request.range.startOffset) || !Number.isInteger(request.range.endOffset) ||
    request.range.startOffset < 0 || request.range.endOffset < request.range.startOffset) {
    throw new Error("Cross-reference request must include a valid active range.");
  }
  const event: WordReferenceEvent = {
    sequence: referenceSequence++,
    type: "insertCrossReference",
    refId: request.refId,
    display: "number",
    range: { ...request.range },
  };
  referenceHistory.push(event);
  return { ...event, range: { ...event.range } };
}

export function getTaskScopedWordReferenceHistory() {
  return referenceHistory.map((event) => event.type === "insertCrossReference"
    ? { ...event, range: { ...event.range } }
    : { ...event });
}

export function resetTaskScopedWordInteractionRequests() {
  pageNumberRequest = null;
  tabStopRequest = null;
  imageRequest = null;
  referenceSequence = 1;
  referenceIdSequence = 1;
  referenceHistory = [];
}
