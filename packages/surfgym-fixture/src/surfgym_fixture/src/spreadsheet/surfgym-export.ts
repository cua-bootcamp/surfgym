import type { Value } from "../external";

export type TaskScopedSpreadsheetExportFormat = "csv" | "pdf";
export type TaskScopedSpreadsheetExportRequest = {
  format: TaskScopedSpreadsheetExportFormat;
  filename: string;
  fitToOnePage?: true;
};

export type TaskScopedSpreadsheetExportResult =
  | { ok: true; request: TaskScopedSpreadsheetExportRequest }
  | { ok: false; message: string };

let currentRequest: TaskScopedSpreadsheetExportRequest | null = null;

export function requestTaskScopedSpreadsheetExport(
  format: string,
  filename: string,
  fitToOnePage: boolean = false,
): TaskScopedSpreadsheetExportResult {
  const validation = validateExportRequest(format, filename, fitToOnePage);
  if (!validation.ok) return validation;

  currentRequest = validation.request;
  return { ok: true, request: { ...currentRequest } };
}

export function getTaskScopedSpreadsheetExportRequest() {
  return currentRequest ? { ...currentRequest } : null;
}

export function setTaskScopedSpreadsheetExportRequest(value: Value) {
  if (value === null) {
    currentRequest = null;
    return null;
  }
  if (!isRecord(value) || typeof value.format !== "string" || typeof value.filename !== "string") {
    throw new Error("Spreadsheet export request must include format and filename strings.");
  }
  if (value.fitToOnePage !== undefined && typeof value.fitToOnePage !== "boolean") {
    throw new Error("Spreadsheet export fitToOnePage must be a boolean when provided.");
  }

  const result = requestTaskScopedSpreadsheetExport(value.format, value.filename, value.fitToOnePage === true);
  if (!result.ok) throw new Error(result.message);
  return result.request;
}

export function resetTaskScopedSpreadsheetExportRequest() {
  currentRequest = null;
}

function validateExportRequest(format: string, filename: string, fitToOnePage: boolean): TaskScopedSpreadsheetExportResult {
  if (format !== "csv" && format !== "pdf") {
    return { ok: false, message: "Export format must be CSV or PDF." };
  }
  if (!filename || filename !== filename.trim() || /[\\/<>:\"|?*\u0000-\u001f]/.test(filename)) {
    return { ok: false, message: "Enter a valid export filename without a path or reserved characters." };
  }
  const extension = filename.slice(filename.lastIndexOf(".") + 1).toLowerCase();
  if (extension !== format) {
    return { ok: false, message: "The filename extension must match the selected export format." };
  }
  if (typeof fitToOnePage !== "boolean") {
    return { ok: false, message: "Fit-to-one-page must be a boolean." };
  }
  if (fitToOnePage && format !== "pdf") {
    return { ok: false, message: "Fit-to-one-page is available only for PDF export." };
  }

  return { ok: true, request: fitToOnePage ? { format, filename, fitToOnePage: true } : { format, filename } };
}

function isRecord(value: Value): value is { [key: string]: Value } {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
