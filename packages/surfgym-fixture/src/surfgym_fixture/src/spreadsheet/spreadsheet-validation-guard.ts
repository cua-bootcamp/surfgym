export const setRangeValuesCommandId = "sheet.command.set-range-values";
export const setRangeValuesMutationId = "sheet.mutation.set-range-values";

export type SpreadsheetValidationListConfig = {
  values: string[];
  allowBlank: boolean;
};

type CommandRange = {
  startRow: number;
  endRow: number;
  startColumn: number;
  endColumn: number;
};

type RangeValueCommand = {
  id?: unknown;
  params?: {
    subUnitId?: unknown;
    range?: unknown;
    value?: unknown;
    cellValue?: unknown;
  };
};

type BeforeCommandEvents = {
  Event: { BeforeCommandExecute: unknown };
  /** FUniver's event-name generic is intentionally opaque at this adapter boundary. */
  addEvent: unknown;
};

type ValidationCommandGuardOptions = {
  commandEvents: BeforeCommandEvents;
  validationForCell: (sheetId: string, row: number, column: number) => SpreadsheetValidationListConfig | null;
  onReject: (message: string) => void;
};

type ProposedCellValue = {
  row: number;
  column: number;
  value: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRange(value: unknown): value is CommandRange {
  return isRecord(value) &&
    ["startRow", "endRow", "startColumn", "endColumn"].every((key) => Number.isInteger(value[key]));
}

function cellInputValue(value: unknown) {
  if (!isRecord(value)) return value;
  return value.v;
}

function matrixCells(value: Record<string, unknown>) {
  const cells: ProposedCellValue[] = [];
  for (const [rowKey, rowValue] of Object.entries(value)) {
    const row = Number(rowKey);
    if (!Number.isInteger(row) || !isRecord(rowValue)) continue;
    for (const [columnKey, cellValue] of Object.entries(rowValue)) {
      const column = Number(columnKey);
      if (!Number.isInteger(column)) continue;
      cells.push({ row, column, value: cellInputValue(cellValue) });
    }
  }
  return cells;
}

function commandCells(range: CommandRange, value: unknown) {
  if (Array.isArray(value)) {
    return value.flatMap((rowValues, rowOffset) => Array.isArray(rowValues)
      ? rowValues.map((cellValue, columnOffset) => ({
        row: range.startRow + rowOffset,
        column: range.startColumn + columnOffset,
        value: cellInputValue(cellValue),
      }))
      : []);
  }
  if (isRecord(value) && !("v" in value) && !("f" in value)) {
    return matrixCells(value);
  }
  return [{ row: range.startRow, column: range.startColumn, value: cellInputValue(value) }];
}

export function validationMessageForValue(value: unknown, validation: SpreadsheetValidationListConfig | null) {
  if (validation === null) return null;
  const normalized = value === null || value === undefined ? "" : String(value);
  if (normalized === "" && !validation.allowBlank) return "A value is required by the validation list.";
  if (normalized !== "" && !validation.values.includes(normalized)) return "Choose a value from the validation list.";
  return null;
}

export function installSpreadsheetValidationCommandGuard({
  commandEvents,
  validationForCell,
  onReject,
}: ValidationCommandGuardOptions) {
  const addEvent = commandEvents.addEvent as (
    eventName: unknown,
    listener: (event: unknown) => void,
  ) => { dispose: () => void };

  return addEvent.call(commandEvents, commandEvents.Event.BeforeCommandExecute, (event) => {
    if (!isRecord(event) || !isRecord(event.params)) return;
    const command = event as RangeValueCommand;
    const sheetId = command.params?.subUnitId;
    if (typeof sheetId !== "string") return;
    const cells = event.id === setRangeValuesCommandId && isRange(command.params?.range)
      ? commandCells(command.params.range, command.params.value)
      : event.id === setRangeValuesMutationId && isRecord(command.params?.cellValue)
        ? matrixCells(command.params.cellValue)
        : [];
    const rejectedCells = cells
      .map((cell) => ({
        ...cell,
        message: validationMessageForValue(cell.value, validationForCell(sheetId, cell.row, cell.column)),
      }))
      .filter((cell) => cell.message !== null);

    if (!rejectedCells.length) return;

    event.cancel = true;
    onReject(rejectedCells[0]!.message!);
  });
}
