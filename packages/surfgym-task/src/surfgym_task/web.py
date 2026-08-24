import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from surfgym_contracts.task import Hook, LifecycleHooks, Task

WEB_STATE_RESET_HOOK = Hook(
    timing="before",
    script=(
        "(async () => { for (let attempt = 0; attempt < 120; attempt += 1) { "
        "if (window.surfgym) return window.surfgym.get({\"$surfgym\":{\"type\":\"release\"}}); "
        "await new Promise((resolve) => setTimeout(resolve, 250)); "
        "} throw new Error('web release bridge was unavailable'); })()"
    ),
)

DOCKER_FIXTURE_RELEASE_HOOK = Hook(
    timing="before",
    script=(
        "(async () => { for (let attempt = 0; attempt < 120; attempt += 1) { "
        "if (window.surfgym) return window.surfgym.get({\"$surfgym\":{\"type\":\"release\"}}); "
        "await new Promise((resolve) => setTimeout(resolve, 250)); "
        "} throw new Error('fixture release bridge was unavailable'); })()"
    ),
)


def load_web_tasks(tasks_dir: Path) -> list[Task]:
    return _load_tasks(tasks_dir, task_kind="web", release_hook=WEB_STATE_RESET_HOOK)


def load_fixture_tasks(tasks_dir: Path) -> list[Task]:
    return _load_tasks(
        tasks_dir,
        task_kind="fixture",
        release_hook=DOCKER_FIXTURE_RELEASE_HOOK,
    )


def _load_tasks(tasks_dir: Path, *, task_kind: str, release_hook: Hook) -> list[Task]:
    task_paths = sorted(tasks_dir.glob("*.json"))
    if not task_paths:
        raise FileNotFoundError(
            f"no {task_kind} task json files found under {tasks_dir}"
        )

    tasks: list[Task] = []
    for task_path in task_paths:
        try:
            payload: object = json.loads(task_path.read_text(encoding="utf-8"))
            tasks.append(_normalize_task(payload, release_hook=release_hook))
        except Exception as exc:
            raise ValueError(
                f"invalid {task_kind} task json {task_path}: {exc}"
            ) from exc

    return tasks


def _normalize_task(raw_payload: object, *, release_hook: Hook) -> Task:
    if not isinstance(raw_payload, Mapping):
        raise ValueError("web task payload must be an object")

    payload = _string_keyed_mapping(cast(Mapping[object, object], raw_payload))
    legacy_hash = payload.pop("hash", None)
    if legacy_hash is not None and legacy_hash != payload.get("task_id"):
        raise ValueError("legacy hash must match task_id")

    payload["website"] = _normalize_website(payload.get("website"))

    hooks = LifecycleHooks.model_validate(payload.get("lifecycle_hooks", {}))
    release_hooks = list(hooks.release)
    if release_hook not in release_hooks:
        release_hooks.append(release_hook)
    payload["lifecycle_hooks"] = hooks.model_copy(update={"release": release_hooks})

    return Task.model_validate(payload)


def _normalize_website(value: object) -> object:
    if not isinstance(value, Mapping):
        return value

    website = _string_keyed_mapping(cast(Mapping[object, object], value))
    fields = set(website)
    if "base" in website:
        unsupported = fields - {"base", "param"}
        if unsupported:
            raise ValueError(f"unsupported website fields: {sorted(unsupported)}")

        base = website["base"]
        params = website.get("param", {})
        if not isinstance(base, str) or not isinstance(params, Mapping):
            raise ValueError("website base must be a string and param must be an object")

        param_items = _string_keyed_mapping(cast(Mapping[object, object], params))
        if not all(isinstance(item, (str, int, float, bool)) for item in param_items.values()):
            raise ValueError("website param values must be scalar")
        parsed = urlsplit(base)
        query = [
            *parse_qsl(parsed.query, keep_blank_values=True),
            *((key, str(item)) for key, item in param_items.items()),
        ]
        return urlunsplit(parsed._replace(query=urlencode(query)))

    unsupported = fields - {"url", "website_id"}
    if unsupported:
        raise ValueError(f"unsupported website fields: {sorted(unsupported)}")
    return [website]


def _string_keyed_mapping(value: Mapping[object, object]) -> dict[str, object]:
    if not all(isinstance(key, str) for key in value):
        raise ValueError("web task object keys must be strings")
    return {str(key): item for key, item in value.items()}
