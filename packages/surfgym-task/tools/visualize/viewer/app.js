const state = { manifest: null, tasks: [], index: 0 };

const elements = {
  sourceMeta: document.querySelector("#sourceMeta"),
  prevButton: document.querySelector("#prevButton"),
  nextButton: document.querySelector("#nextButton"),
  counter: document.querySelector("#counter"),
  emptyState: document.querySelector("#emptyState"),
  screenshot: document.querySelector("#screenshot"),
  taskId: document.querySelector("#taskId"),
  website: document.querySelector("#website"),
  instruction: document.querySelector("#instruction"),
  rules: document.querySelector("#rules"),
  status: document.querySelector("#status"),
  setup: document.querySelector("#setup"),
  errors: document.querySelector("#errors")
};

init();

async function init() {
  try {
    const response = await fetch("../data/tasks.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.manifest = await response.json();
    state.tasks = Array.isArray(state.manifest.tasks) ? state.manifest.tasks : [];
    render();
  } catch (error) {
    showEmptyState(error);
  }

  elements.prevButton.addEventListener("click", () => move(-1));
  elements.nextButton.addEventListener("click", () => move(1));
  document.addEventListener("keydown", handleKeyDown);
}

function render() {
  if (state.tasks.length === 0) {
    const manifestError = state.manifest?.error;
    const message = manifestError ? `${manifestError.stage}: ${manifestError.message}` : "No tasks in data/tasks.json";
    showEmptyState(new Error(message));
    return;
  }

  const task = state.tasks[state.index];
  const capture = task.capture ?? {};
  const rules = task.rules ?? task.task?.evaluation?.rules ?? task.task?.rules ?? [];

  elements.emptyState.hidden = true;
  elements.screenshot.hidden = false;
  elements.screenshot.src = `../${task.screenshot}`;
  elements.screenshot.alt = `Screenshot for ${task.task_id}`;

  elements.sourceMeta.textContent = [state.manifest?.source?.input ? `Source: ${state.manifest.source.input}` : null, `Captured: ${state.tasks.length}`, "Use ArrowLeft and ArrowRight to browse"].filter(Boolean).join(" | ");

  elements.counter.textContent = `${state.index + 1} / ${state.tasks.length}`;
  elements.prevButton.disabled = state.index === 0;
  elements.nextButton.disabled = state.index === state.tasks.length - 1;

  elements.taskId.textContent = task.task_id ?? "-";
  elements.website.textContent = task.website ?? "Website";
  elements.website.href = task.website ?? "#";
  elements.instruction.textContent = task.instruction ?? "";
  elements.rules.textContent = JSON.stringify(rules, null, 2);

  elements.status.textContent = capture.status ?? "-";
  elements.status.className = capture.status === "error" ? "statusError" : "";
  elements.setup.textContent = capture.setupRan ? "ran" : task.setup ? "not run" : "none";
  elements.errors.textContent = Array.isArray(capture.errors) && capture.errors.length > 0 ? capture.errors.join("\n") : "none";
}

function move(delta) {
  const nextIndex = state.index + delta;
  if (nextIndex < 0 || nextIndex >= state.tasks.length) return;
  state.index = nextIndex;
  render();
}

function handleKeyDown(event) {
  if (event.key === "ArrowLeft") move(-1);
  if (event.key === "ArrowRight") move(1);
  if (event.key === "Home") {
    state.index = 0;
    render();
  }
  if (event.key === "End") {
    state.index = Math.max(0, state.tasks.length - 1);
    render();
  }
}

function showEmptyState(error) {
  elements.sourceMeta.textContent = `Capture data unavailable: ${error.message}`;
  elements.counter.textContent = "0 / 0";
  elements.prevButton.disabled = true;
  elements.nextButton.disabled = true;
  elements.emptyState.hidden = false;
  elements.screenshot.hidden = true;
  elements.taskId.textContent = "-";
  elements.website.textContent = "Website";
  elements.website.href = "#";
  elements.instruction.textContent = "";
  elements.rules.textContent = "";
  elements.status.textContent = "-";
  elements.setup.textContent = "-";
  elements.errors.textContent = error.message;
}
