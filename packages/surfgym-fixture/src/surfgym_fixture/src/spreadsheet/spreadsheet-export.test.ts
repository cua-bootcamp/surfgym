import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { get, set } from "./external";
import {
  getTaskScopedSpreadsheetExportRequest,
  resetTaskScopedSpreadsheetExportRequest,
  requestTaskScopedSpreadsheetExport,
} from "./surfgym-export";
import { renderSpreadsheetMockToolbar } from "./spreadsheet-ui";

const exportSpec = { kind: "export" as const, property: "request" as const };

beforeEach(() => {
  document.body.innerHTML = '<div id="toolbar"></div>';
  resetTaskScopedSpreadsheetExportRequest();
});

afterEach(() => {
  document.body.innerHTML = "";
  resetTaskScopedSpreadsheetExportRequest();
});

describe("task-scoped Spreadsheet export request", () => {
  it("records a confirmed one-page PDF request", () => {
    expect(requestTaskScopedSpreadsheetExport("pdf", "Project_Budget.pdf", true)).toEqual({
      ok: true,
      request: { format: "pdf", filename: "Project_Budget.pdf", fitToOnePage: true },
    });
  });

  it("passes an explicitly checked one-page option from the Export dialog", () => {
    renderSpreadsheetMockToolbar({ containerId: "toolbar" });
    document.querySelector<HTMLButtonElement>('[data-spreadsheet-export]')?.click();
    const dialog = document.querySelector<HTMLElement>('[data-spreadsheet-export-dialog]');
    const filename = dialog?.querySelector<HTMLInputElement>('[data-spreadsheet-export-filename]');
    const fitToOnePage = dialog?.querySelector<HTMLInputElement>('[data-spreadsheet-export-fit-to-one-page]');
    if (!dialog || !filename || !fitToOnePage) throw new Error("One-page export controls were not rendered.");

    filename.value = "Project_Budget.pdf";
    fitToOnePage.checked = true;
    dialog.querySelector<HTMLButtonElement>('[data-spreadsheet-export-confirm]')?.click();

    expect(get(exportSpec)).toEqual({ format: "pdf", filename: "Project_Budget.pdf", fitToOnePage: true });
  });

  it("rejects fit-to-one-page for CSV without replacing prior state", () => {
    requestTaskScopedSpreadsheetExport("pdf", "baseline.pdf", true);

    expect(requestTaskScopedSpreadsheetExport("csv", "baseline.csv", true)).toMatchObject({ ok: false });
    expect(getTaskScopedSpreadsheetExportRequest()).toEqual({
      format: "pdf", filename: "baseline.pdf", fitToOnePage: true,
    });
  });

  it("records the confirmed CSV format and filename through the canonical get surface", () => {
    renderSpreadsheetMockToolbar({ containerId: "toolbar" });

    document.querySelector<HTMLButtonElement>('[data-spreadsheet-export]')?.click();
    const dialog = document.querySelector<HTMLElement>('[data-spreadsheet-export-dialog]');
    expect(dialog).not.toBeNull();
    expect(get(exportSpec)).toBeNull();

    const format = dialog?.querySelector<HTMLSelectElement>('[data-spreadsheet-export-format]');
    const filename = dialog?.querySelector<HTMLInputElement>('[data-spreadsheet-export-filename]');
    if (!dialog || !format || !filename) throw new Error("Export controls were not rendered.");
    format.value = "csv";
    format.dispatchEvent(new Event("change", { bubbles: true }));
    filename.value = "quarterly-summary.csv";
    dialog.querySelector<HTMLButtonElement>('[data-spreadsheet-export-confirm]')?.click();

    expect(document.querySelector('[data-spreadsheet-export-dialog]')).toBeNull();
    expect(get(exportSpec)).toEqual({ format: "csv", filename: "quarterly-summary.csv" });
  });

  it("keeps the prior request when the final filename is invalid", () => {
    expect(requestTaskScopedSpreadsheetExport("pdf", "baseline.pdf")).toEqual({
      ok: true,
      request: { format: "pdf", filename: "baseline.pdf" },
    });
    renderSpreadsheetMockToolbar({ containerId: "toolbar" });

    document.querySelector<HTMLButtonElement>('[data-spreadsheet-export]')?.click();
    const dialog = document.querySelector<HTMLElement>('[data-spreadsheet-export-dialog]');
    const filename = dialog?.querySelector<HTMLInputElement>('[data-spreadsheet-export-filename]');
    if (!dialog || !filename) throw new Error("Export controls were not rendered.");
    filename.value = "../replacement.pdf";
    dialog.querySelector<HTMLButtonElement>('[data-spreadsheet-export-confirm]')?.click();

    expect(dialog.querySelector('[role="alert"]')?.textContent).toContain("filename");
    expect(getTaskScopedSpreadsheetExportRequest()).toEqual({ format: "pdf", filename: "baseline.pdf" });
  });

  it("rejects unsupported formats and mismatched extensions without recording", () => {
    expect(requestTaskScopedSpreadsheetExport("xlsx", "report.xlsx")).toEqual({
      ok: false,
      message: "Export format must be CSV or PDF.",
    });
    expect(requestTaskScopedSpreadsheetExport("csv", "report.pdf")).toEqual({
      ok: false,
      message: "The filename extension must match the selected export format.",
    });
    expect(getTaskScopedSpreadsheetExportRequest()).toBeNull();
  });

  it("round-trips valid requests and rejects invalid payloads through external state", () => {
    expect(set(exportSpec, { format: "pdf", filename: "audit.pdf" })).toEqual({
      format: "pdf",
      filename: "audit.pdf",
    });
    expect(get(exportSpec)).toEqual({ format: "pdf", filename: "audit.pdf" });
    expect(() => set(exportSpec, { format: "csv", filename: "audit.pdf" })).toThrow(
      "filename extension must match",
    );
    expect(get(exportSpec)).toEqual({ format: "pdf", filename: "audit.pdf" });
  });
});
