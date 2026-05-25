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
  seedPath: string;
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

  const filteredTasks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const tasks = runDetail?.tasks ?? [];
    if (!normalizedQuery) return tasks;

    return tasks.filter(
      (task) =>
        task.taskId.toLowerCase().includes(normalizedQuery) ||
        task.instruction.toLowerCase().includes(normalizedQuery)
    );
  }, [query, runDetail?.tasks]);

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

      <section className="flex-1 flex flex-col h-full">
        <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
          {selectedTask ? (
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0">
                <h2 className="truncate text-xl font-semibold">{selectedTask.taskId}</h2>
                <p className="mt-1 truncate text-sm text-slate-500">
                  Editing `instruction.jsonc` via key: {selectedTask.instructionKey ?? "not mapped"}
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

        <div className="flex flex-col flex-1 gap-4 p-4">
          
          <section className="rounded-md border border-slate-200 bg-white collapse-0">
            <div className="border-b border-slate-200 px-4 py-3">
              <div className="text-sm font-semibold">Instruction</div>
              <div className="mt-1 text-xs text-slate-500">
                Save writes to {runDetail?.instructionPath ?? "instruction.jsonc"}
              </div>
            </div>

            <textarea
              className="min-h-0 w-full resize-none border-0 p-4 text-sm leading-6 outline-none"
              value={draftInstruction}
              disabled={!selectedTask}
              onChange={(event) => {
                setDraftInstruction(event.target.value);
                setSaveState("idle");
              }}
            />

            <div className="flex min-h-12 items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
              <span>
                {dirty ? "Unsaved changes" : saveState === "saved" ? "Saved" : "No changes"}
              </span>
              <span>Reward {selectedTask?.reward}</span>
            </div>
          </section>

          <section className="grid flex-1 rounded-md border border-slate-200 bg-white">
            {/* <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-4 py-3">
              <div>
                <div className="text-sm font-semibold">Screenshots</div>
                <div className="mt-1 text-xs text-slate-500">
                  {selectedTask?.screenshots.length ?? 0} captured steps
                </div>
              </div>

              <div className="flex flex-wrap justify-end gap-2">
                {selectedTask?.screenshots.map((screenshot, index) => (
                  <button
                    key={screenshot}
                    className={[
                      "h-8 rounded-md border px-3 text-xs font-medium",
                      selectedScreenshotIndex === index
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                    ].join(" ")}
                    onClick={() => setSelectedScreenshotIndex(index)}
                  >
                    {index}
                  </button>
                ))}
              </div>
            </div> */}

            <div className="min-h-0 flex flex-row overflow-y-auto bg-slate-50 p-3">
              {
                selectedTask?.screenshots.map(s => <img
                  className="w-1/2 rounded border border-slate-200 bg-white object-contain"
                  src={s}
                />)
              }
        
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
