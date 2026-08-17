export type TaskScopedLineSparkline = {
  sourceRange: string | null;
  type: "line" | null;
};

export type TaskScopedLineSparklineEntry = TaskScopedLineSparkline & {
  sheet: string;
  cell: string;
};

function normalizeSheet(sheet: string | number | undefined) {
  return sheet === undefined ? "Sheet1" : String(sheet);
}

function normalizeCell(cell: string) {
  const normalized = cell.trim().toUpperCase();
  if (!/^[A-Z]+[1-9]\d*$/.test(normalized)) throw new Error("Sparkline target must be an A1 cell.");
  return normalized;
}

function sparklineKey(sheet: string | number | undefined, cell: string) {
  return `${normalizeSheet(sheet)}!${normalizeCell(cell)}`;
}

function clone(value: TaskScopedLineSparkline): TaskScopedLineSparkline {
  return { ...value };
}

export class TaskScopedLineSparklineRegistry {
  private readonly sparklines = new Map<string, TaskScopedLineSparkline>();
  private readonly listeners = new Set<() => void>();

  onChange(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    for (const listener of this.listeners) listener();
  }

  get(sheet: string | number | undefined, cell: string) {
    return clone(this.sparklines.get(sparklineKey(sheet, cell)) ?? { sourceRange: null, type: null });
  }

  listAll(): TaskScopedLineSparklineEntry[] {
    return [...this.sparklines.entries()].map(([key, sparkline]) => {
      const separator = key.lastIndexOf("!");
      return {
        ...clone(sparkline),
        sheet: key.slice(0, separator),
        cell: key.slice(separator + 1),
      };
    });
  }

  set(
    sheet: string | number | undefined,
    cell: string,
    property: keyof TaskScopedLineSparkline,
    value: unknown,
  ) {
    const key = sparklineKey(sheet, cell);
    const next = this.get(sheet, cell);
    if (property === "sourceRange") {
      if (typeof value !== "string" || !value.trim()) throw new Error("Sparkline source range must be non-empty.");
      next.sourceRange = value.trim();
      next.type ??= "line";
    } else {
      if (value !== "line") throw new Error("Only the seed-required line sparkline type is supported.");
      next.type = "line";
    }
    this.sparklines.set(key, next);
    this.notify();
    return clone(next);
  }

  reset() {
    this.sparklines.clear();
    this.notify();
  }
}

export const taskScopedLineSparklines = new TaskScopedLineSparklineRegistry();

export function getTaskScopedSparklineMeta(sheet: string | number | undefined, cell: string) {
  return taskScopedLineSparklines.get(sheet, cell);
}

export function setTaskScopedSparklineMeta(
  sheet: string | number | undefined,
  cell: string,
  property: keyof TaskScopedLineSparkline,
  value: unknown,
) {
  return taskScopedLineSparklines.set(sheet, cell, property, value);
}

export function resetTaskScopedSparklines() {
  taskScopedLineSparklines.reset();
}
