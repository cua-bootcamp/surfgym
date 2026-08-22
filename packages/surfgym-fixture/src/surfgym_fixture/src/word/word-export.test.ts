import { afterEach, describe, expect, it, vi } from "vitest";
import { get, set } from "./external";
import { _recordPdfExportRequest, WordRuntimeStore } from "./internal";
import { renderWordMockToolbar } from "./word-ui";

type RuntimeStoreInternals = {
  _runtime: unknown;
};

const runtimeStoreInternals = WordRuntimeStore as unknown as RuntimeStoreInternals;
let restoreWordRuntime: (() => void) | undefined;

function initialSnapshot(): Record<string, unknown> {
  return {
    id: "word-export-test",
    documentStyle: {},
    body: {
      dataStream: "Quarterly report\r\n",
      textRuns: [{ st: 0, ed: 16, ts: { ff: "Arial" } }],
      paragraphs: [{ startIndex: 16, paragraphStyle: { lineSpacing: 1.5 } }]
    }
  };
}

function installWordRuntime(snapshotValue: Record<string, unknown>) {
  const previousRuntime = runtimeStoreInternals._runtime;
  let snapshot = structuredClone(snapshotValue);
  const reset = vi.fn((nextSnapshot: Record<string, unknown>) => {
    snapshot = structuredClone(nextSnapshot);
  });
  const documentModel = {
    getSnapshot: () => structuredClone(snapshot),
    reset
  };

  WordRuntimeStore.runtime = {
    univer: {},
    univerAPI: {},
    document: { doc: documentModel }
  } as never;

  return {
    getSnapshot: () => structuredClone(snapshot),
    reset,
    restore: () => {
      runtimeStoreInternals._runtime = previousRuntime;
    }
  };
}

afterEach(() => {
  document.body.innerHTML = "";
  restoreWordRuntime?.();
  restoreWordRuntime = undefined;
});

describe("Word PDF export request", () => {
  it("records a normalized canonical request only after final UI confirmation", () => {
    const runtime = installWordRuntime(initialSnapshot());
    restoreWordRuntime = runtime.restore;
    document.body.innerHTML = '<div id="toolbar"></div>';

    renderWordMockToolbar({
      containerId: "toolbar",
      recordPdfExportRequest: _recordPdfExportRequest
    });

    const exportButton = document.querySelector<HTMLButtonElement>(
      '[data-word-action="exportPdf"]'
    )!;
    expect(exportButton.getAttribute("aria-disabled")).toBe("false");
    exportButton.click();
    expect(runtime.reset).not.toHaveBeenCalled();
    expect(get({ kind: "document", property: "pdfExportRequest" })).toBeNull();

    document.querySelector<HTMLButtonElement>("[data-word-export-pdf-cancel]")!.click();
    expect(document.getElementById("word-mock-export-pdf-dialog")).toBeNull();
    expect(runtime.reset).not.toHaveBeenCalled();

    exportButton.click();
    const input = document.querySelector<HTMLInputElement>("[data-word-export-pdf-filename]")!;
    input.value = "  ";
    document.querySelector<HTMLButtonElement>("[data-word-export-pdf-confirm]")!.click();
    expect(runtime.reset).not.toHaveBeenCalled();
    expect(get({ kind: "document", property: "pdfExportRequest" })).toBeNull();
    expect(
      document.querySelector<HTMLElement>("[data-word-export-pdf-error]")!.textContent
    ).toContain("file name is required");

    input.value = "  quarterly-report  ";
    document.querySelector<HTMLButtonElement>("[data-word-export-pdf-confirm]")!.click();
    expect(runtime.reset).toHaveBeenCalledOnce();
    expect(get({ kind: "document", property: "pdfExportRequest" })).toEqual({
      format: "pdf",
      fileName: "quarterly-report.pdf"
    });
    expect(document.getElementById("word-mock-export-pdf-dialog")).toBeNull();

    const snapshot = runtime.getSnapshot() as Record<string, unknown>;
    expect(snapshot.body).toEqual(initialSnapshot().body);
    runtime.restore();
    const reloadedRuntime = installWordRuntime(snapshot);
    restoreWordRuntime = reloadedRuntime.restore;
    expect(get({ kind: "document", property: "pdfExportRequest" })).toEqual({
      format: "pdf",
      fileName: "quarterly-report.pdf"
    });
  });

  it("rejects invalid and direct-set requests without mutating canonical state", () => {
    const runtime = installWordRuntime(initialSnapshot());
    restoreWordRuntime = runtime.restore;

    expect(() => _recordPdfExportRequest("folder/report.pdf")).toThrow(
      "Invalid PDF export file name"
    );
    expect(() =>
      set(
        { kind: "document", property: "pdfExportRequest" },
        { format: "pdf", fileName: "bypass.pdf" }
      )
    ).toThrow("must be confirmed through the UI");
    expect(runtime.reset).not.toHaveBeenCalled();
    expect(get({ kind: "document", property: "pdfExportRequest" })).toBeNull();
  });
});
