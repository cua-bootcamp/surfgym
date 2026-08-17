import { describe, expect, it, vi } from "vitest";
import {
  installSpreadsheetValidationCommandGuard,
  setRangeValuesMutationId,
  setRangeValuesCommandId,
} from "./spreadsheet-validation-guard";

type CommandListener = (event: unknown) => void;

function installGuard() {
  let listener: CommandListener | undefined;
  let addEventThis: unknown;
  const onReject = vi.fn();
  const dispose = vi.fn();
  const commandEvents = {
    Event: { BeforeCommandExecute: "before-command" },
    addEvent(this: unknown, eventName: unknown, nextListener: CommandListener) {
      addEventThis = this;
      expect(eventName).toBe("before-command");
      listener = nextListener;
      return { dispose };
    },
  };

  installSpreadsheetValidationCommandGuard({
    commandEvents,
    validationForCell: (sheetId, row, column) =>
      sheetId === "sheet-1" && row === 1 && column === 3
        ? { values: ["Pass", "Fail", "Held"], allowBlank: false }
        : null,
    onReject,
  });

  return {
    emit(event: unknown) {
      expect(addEventThis).toBe(commandEvents);
      const cancellableEvent = { ...(event as Record<string, unknown>), cancel: false };
      listener!(cancellableEvent);
      return cancellableEvent;
    },
    onReject,
    dispose,
  };
}

describe("real grid validation command guard", () => {
  it("cancels a disallowed grid value before the native command can replace an existing cell", () => {
    const guard = installGuard();

    const event = guard.emit({
      id: setRangeValuesCommandId,
      params: {
        subUnitId: "sheet-1",
        range: { startRow: 1, endRow: 1, startColumn: 3, endColumn: 3 },
        value: { v: "Other" },
      },
    });

    expect(event.cancel).toBe(true);
    expect(guard.onReject).toHaveBeenCalledWith("Choose a value from the validation list.");
  });

  it("does not cancel a native grid commit accepted by the selected list", () => {
    const guard = installGuard();

    const event = guard.emit({
      id: setRangeValuesCommandId,
      params: {
        subUnitId: "sheet-1",
        range: { startRow: 1, endRow: 1, startColumn: 3, endColumn: 3 },
        value: { v: "Pass" },
      },
    });

    expect(event.cancel).toBe(false);
    expect(guard.onReject).not.toHaveBeenCalled();
  });

  it("cancels the native range-values mutation form emitted by cell editing", () => {
    const guard = installGuard();

    const event = guard.emit({
      id: setRangeValuesMutationId,
      params: {
        subUnitId: "sheet-1",
        cellValue: { 1: { 3: { v: "Other" } } },
      },
    });

    expect(event.cancel).toBe(true);
    expect(guard.onReject).toHaveBeenCalledWith("Choose a value from the validation list.");
  });
});
