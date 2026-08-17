import { describe, expect, it } from "vitest";
import { TaskScopedLineSparklineRegistry } from "./surfgym-sparkline";

describe("task-scoped line sparkline canonical state", () => {
  it("keeps the warehouse F2:F9 targets and their row source ranges independently", () => {
    const sparklines = new TaskScopedLineSparklineRegistry();

    for (let row = 2; row <= 9; row += 1) {
      sparklines.set("Sheet1", `F${row}`, "sourceRange", `C${row}:E${row}`);
      sparklines.set("Sheet1", `F${row}`, "type", "line");
    }

    expect(sparklines.get("Sheet1", "F2")).toEqual({ sourceRange: "C2:E2", type: "line" });
    expect(sparklines.get("Sheet1", "F9")).toEqual({ sourceRange: "C9:E9", type: "line" });
  });

  it("rejects types outside the current line-only seed inventory and resets cleanly", () => {
    const sparklines = new TaskScopedLineSparklineRegistry();
    sparklines.set("Sheet1", "F2", "sourceRange", "C2:E2");

    expect(() => sparklines.set("Sheet1", "F2", "type", "column" as never)).toThrow("line");
    sparklines.reset();
    expect(sparklines.get("Sheet1", "F2")).toEqual({ sourceRange: null, type: null });
  });
});
