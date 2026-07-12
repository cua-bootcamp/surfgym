import { useEffect, useMemo, useState } from "react";
import { Sidebar } from "./sidebar";

export type RunSummary = { total: number; reward_sum: number; task_source: string };

export type SnapshotRun = { id: string; summary: RunSummary };

export type SnapshotTask = {
  taskId: string;
  reward: number;
  instructionKey: string | null;
  instruction: string;
  sourceInstruction: string;
  screenshots: string[];
};

type SnapshotRunDetail = SnapshotRun & {
  instructionPath: string;
  taskSourcePath: string;
  tasks: SnapshotTask[];
};

type SaveState = "idle" | "saving" | "saved" | "error";

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function App() {
  const [runs, setRuns] = useState<SnapshotRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [runDetail, setRunDetail] = useState<SnapshotRunDetail | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [query, setQuery] = useState("");
  const [draftInstruction, setDraftInstruction] = useState("");
  const [selectedScreenshotIndex, setSelectedScreenshotIndex] = useState(0);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState("");

  const selectedTask = useMemo(
    () => runDetail?.tasks.find((task) => task.taskId === selectedTaskId) ?? null,
    [runDetail, selectedTaskId]
  );

  const selectedTaskIndex = useMemo(
    () => runDetail?.tasks.findIndex((task) => task.taskId === selectedTaskId) ?? -1,
    [runDetail, selectedTaskId]
  );

  const dirty =
    selectedTask !== null && draftInstruction.trim() !== selectedTask.instruction.trim();

  useEffect(() => {
    api<SnapshotRun[]>("/api/runs")
      .then((nextRuns) => {
        setRuns(nextRuns);
        setSelectedRunId(nextRuns[0]?.id ?? "");
      })
      .catch((nextError: unknown) => {
        setError(nextError instanceof Error ? nextError.message : "Failed to load snapshot runs.");
      });
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;

    setError("");
    setRunDetail(null);
    api<SnapshotRunDetail>(`/api/runs/${encodeURIComponent(selectedRunId)}`)
      .then((detail) => {
        setRunDetail(detail);
        setSelectedTaskId(detail.tasks[0]?.taskId ?? "");
      })
      .catch((nextError: unknown) => {
        setError(nextError instanceof Error ? nextError.message : "Failed to load snapshot run.");
      });
  }, [selectedRunId]);

  useEffect(() => {
    setDraftInstruction(selectedTask?.instruction ?? "");
    setSelectedScreenshotIndex(0);
    setSaveState("idle");
  }, [selectedTask?.taskId, selectedTask?.instruction]);

  useEffect(() => {
    function isEditableTarget(target: EventTarget | null) {
      if (!(target instanceof HTMLElement)) return false;
      return (
        target.isContentEditable ||
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement
      );
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (isEditableTarget(event.target)) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;

      const tasks = runDetail?.tasks ?? [];
      if (tasks.length === 0 || selectedTaskIndex < 0) return;

      const direction = event.key === "ArrowRight" ? 1 : -1;
      const nextIndex = (selectedTaskIndex + direction + tasks.length) % tasks.length;
      setSelectedTaskId(tasks[nextIndex].taskId);
      event.preventDefault();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [runDetail?.tasks, selectedTaskIndex]);

  async function saveInstruction() {
    if (!selectedTask?.instructionKey || !dirty) return;

    setSaveState("saving");
    setError("");

    try {
      await api(`/api/instructions/${encodeURIComponent(selectedTask.instructionKey)}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ instruction: draftInstruction.trim() })
      });

      setRunDetail((current) => {
        if (!current) return current;
        return {
          ...current,
          tasks: current.tasks.map((task) =>
            task.taskId === selectedTask.taskId
              ? { ...task, instruction: draftInstruction.trim() }
              : task
          )
        };
      });
      setSaveState("saved");
    } catch (nextError) {
      setSaveState("error");
      setError(nextError instanceof Error ? nextError.message : "Failed to save instruction.");
    }
  }

  return (
    <main className="h-screen w-full flex flex-row bg-slate-100 text-slate-900 overflow-hidden">
      <Sidebar
        runs={runs}
        selectedRunId={selectedRunId}
        summary={runDetail?.summary ?? null}
        tasks={runDetail?.tasks ?? []}
        selectedTaskId={selectedTaskId}
        setSelectedRunId={setSelectedRunId}
        setSelectedTaskId={setSelectedTaskId}
        onSelectRun={setSelectedRunId}
        onSelectTask={setSelectedTaskId}
      />

      <section className="flex-1 flex flex-col h-full min-h-0">
        <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
          {selectedTask ? (
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0">
                <h2 className="truncate text-xl font-semibold">{selectedTask.taskId}</h2>
                <p className="mt-2 max-w-5xl text-sm leading-5 text-slate-600">
                  {selectedTask.instruction}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  className="h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-default disabled:opacity-50"
                  disabled={!dirty}
                  onClick={() => setDraftInstruction(selectedTask.instruction)}
                >
                  Reset
                </button>
                <button
                  className="h-10 rounded-md bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-default disabled:bg-slate-400"
                  disabled={!selectedTask.instructionKey || !dirty || saveState === "saving"}
                  onClick={() => void saveInstruction()}
                >
                  {saveState === "saving" ? "Saving" : "Save"}
                </button>
              </div>
            </div>
          ) : (
            <h2 className="text-xl font-semibold">Select a snapshot task</h2>
          )}
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
          <section className="min-h-0 flex-1 overflow-hidden rounded-md border border-slate-200 bg-white">
            <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto bg-slate-50 p-3">
              {selectedTask?.screenshots.map((s) => (
                <img
                  key={s}
                  className="w-full rounded border border-slate-200 bg-white object-contain"
                  src={s}
                />
              ))}
            </div>
          </section>
        </div>

        {error ? (
          <div className="fixed bottom-4 right-4 max-w-xl rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-sm">
            {error}
          </div>
        ) : null}
      </section>
    </main>
  );
}
