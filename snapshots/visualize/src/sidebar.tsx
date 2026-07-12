import { useMemo, useState } from "react";
import type { SnapshotRun, SnapshotTask, RunSummary } from "./App";

type SidebarProps = {
  runs: SnapshotRun[];
  selectedRunId: string;
  setSelectedRunId: (value: string) => void;
  summary: RunSummary | null;
  tasks: SnapshotTask[];
  selectedTaskId: string;
  setSelectedTaskId: (value: string) => void;
  onSelectRun: (runId: string) => void;
  onSelectTask: (taskId: string) => void;
};

export function Sidebar({
  runs,
  selectedRunId,
  setSelectedRunId,
  summary,
  tasks,
  selectedTaskId,
  setSelectedTaskId,
  onSelectRun,
  onSelectTask
}: SidebarProps) {
  const [query, setQuery] = useState("");

  const filteredTasks = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tasks;

    return tasks.filter(
      (task) => task.taskId.toLowerCase().includes(q) || task.instruction.toLowerCase().includes(q)
    ).sort((a, b) =>
      a.taskId.localeCompare(b.taskId, undefined, { numeric: true })
    );
  }, [query, tasks]);

  return (
    <aside className="h-full w-[400px] shrink-0 flex flex-col border-r overflow-hidden border-slate-200 bg-white">
      <div className="space-y-4 shrink-0 border-b border-slate-200 px-5 py-4">
        <label className="grid gap-1.5 text-sm font-medium text-slate-700">
          Snapshot run
          <select
            className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm outline-none"
            value={selectedRunId}
            onChange={(event) => setSelectedRunId(event.target.value)}
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.id}
              </option>
            ))}
          </select>
        </label>

        <div className="flex flex-row gap-2 text-sm">
          <div className="rounded-md w-full border border-slate-200 bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Reward</div>
            <div className="mt-1 text-lg font-semibold">{summary?.reward_sum ?? 0}</div>
          </div>
          <div className="rounded-md border w-full border-slate-200 bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Tasks</div>
            <div className="mt-1 text-lg font-semibold">{summary?.total ?? 0}</div>
          </div>
        </div>

        <input
          className="w-full h-10 rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          placeholder="Filter task or instruction"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="flex-1 px-3 py-3 overflow-y-auto">
        <div className="">
          {filteredTasks.map((task) => (
            <button
              key={task.taskId}
              className={[
                "flex flex-row h-14 w-full justify-end gap-3 rounded-md border px-3 py-2 text-left text-sm items-center",
                task.taskId === selectedTaskId
                  ? "border-blue-500 bg-blue-50 text-blue-950"
                  : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50"
              ].join(" ")}
              onClick={() => setSelectedTaskId(task.taskId)}
            >
              <span className="flex-1 truncate font-medium">{task.taskId}</span>
              <span
                className={[
                  "rounded px-2 py-1 text-xs font-semibold",
                  task.reward >= 1 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
                ].join(" ")}
              >
                {task.reward}
              </span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
