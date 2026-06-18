from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json5
from playwright.async_api import BrowserContext, Page, async_playwright
from surfgym_contracts.task import (
    Action,
    ChromiumRule,
    ConsoleRule,
    DomRule,
    Evaluation,
    Observation,
    ProfileSetup,
    Task,
    TaskRowsAdapter,
    Value,
    Website,
)

from surfgym_runtime.support.chromium_profile import (
    apply_chromium_profile_file_setup,
    apply_chromium_runtime_profile_setup,
    evaluate_chromium_profile_rule,
)
from surfgym_runtime.support.evaluator import evaluate_page_rules


@dataclass(frozen=True)
class CheckResult:
    index: int
    mode: str
    rule_type: str | None
    expected: Value
    observed: Observation
    passed: bool
    file: str | None = None
    path: str | None = None
    query: str | None = None
    domain: str | None = None
    note: str | None = None


def main() -> None:
    args = _parse_args()
    task = _select_task(_load_tasks(args.task_path), args.task_id)

    if args.evaluate_only is not None:
        checks, reward = _evaluate_profile(task.evaluation, args.evaluate_only)
        _print_result(task, args.evaluate_only, checks, reward)
        raise SystemExit(0 if reward == 1.0 or not args.fail_on_zero else 1)

    reward = asyncio.run(_run_interactive_eval(task, args))
    raise SystemExit(0 if reward == 1.0 or not args.fail_on_zero else 1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a Chromium task for manual solving, then evaluate profile rules."
    )
    parser.add_argument("task_path", type=Path)
    parser.add_argument("--task-id", type=str, default=None)
    parser.add_argument("--profile-dir", type=Path, default=None)
    parser.add_argument("--evaluate-only", type=Path, default=None)
    parser.add_argument("--keep-profile", action="store_true")
    parser.add_argument("--skip-profile-setup", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--channel", type=str, default=None)
    parser.add_argument("--fail-on-zero", action="store_true")
    return parser.parse_args()


async def _run_interactive_eval(task: Task, args: argparse.Namespace) -> float:
    profile_dir, owns_profile_dir = _resolve_profile_dir(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not args.skip_profile_setup:
            _apply_profile_setup(profile_dir, task.profile_setup)

        print(f"Task: {task.task_id}")
        print(f"Instruction: {task.instruction}")
        print(f"Profile: {profile_dir}")
        print("A Chromium window will open. Solve the task there, then return here.")

        async with async_playwright() as playwright:
            launch_kwargs: dict[str, Any] = {
                "headless": args.headless,
                "viewport": {"width": 1920, "height": 1080},
            }
            if args.channel is not None:
                launch_kwargs["channel"] = args.channel

            context = await playwright.chromium.launch_persistent_context(
                profile_dir,
                **launch_kwargs,
            )
            try:
                await apply_chromium_runtime_profile_setup(context, task.profile_setup)
                await _open_websites(context, task.website)
                await _run_setup_actions(context, task.setup)
                await asyncio.to_thread(
                    input,
                    "Press Enter to evaluate after you finish the task...",
                )
                await asyncio.sleep(0.2)
                runtime_observations = await _collect_runtime_observations(context, task.evaluation)
            finally:
                await context.close()

        checks, reward = _evaluate_profile(
            task.evaluation,
            profile_dir,
            runtime_observations=runtime_observations,
        )
        _print_result(task, profile_dir, checks, reward)
        return reward
    finally:
        if owns_profile_dir and not args.keep_profile:
            shutil.rmtree(profile_dir, ignore_errors=True)
        elif args.keep_profile or not owns_profile_dir:
            print(f"Profile kept at: {profile_dir}")


def _resolve_profile_dir(profile_dir: Path | None) -> tuple[Path, bool]:
    if profile_dir is not None:
        return profile_dir.resolve(), False
    return Path(tempfile.mkdtemp(prefix="surfgym-manual-chromium-")), True


async def _open_websites(context: BrowserContext, websites: list[Website]) -> None:
    existing_pages = list(context.pages)

    for idx, website in enumerate(websites):
        if idx < len(existing_pages):
            page = existing_pages[idx]
        else:
            page = await context.new_page()

        await _goto(page, website.url)


async def _run_setup_actions(context: BrowserContext, actions: list[Action] | None) -> None:
    if actions is None:
        return

    for action in actions:
        if action.mode != "playwright":
            raise ValueError("manual_chromium_eval supports playwright setup actions only.")
        await _run_playwright_setup_action(context, action.script)


async def _run_playwright_setup_action(context: BrowserContext, script: str) -> None:
    if script == "close_last_tab":
        pages = list(context.pages)
        if not pages:
            return
        await pages[-1].close()
        remaining_pages = list(context.pages)
        if remaining_pages:
            await remaining_pages[-1].bring_to_front()
        return

    raise ValueError(f"Unsupported manual Chromium setup action: {script}")


async def _goto(page: Page, url: str) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded")
    except Exception:
        await page.goto(url)


def _load_tasks(path: Path) -> list[Task]:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if suffix in {".jsonl", ".ndjson"}:
        payload: object = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == ".jsonc":
        payload = json5.loads(text)
    elif suffix == ".json":
        payload = json.loads(text)
    else:
        raise ValueError(f"Unsupported task file type: {path.suffix}")

    if isinstance(payload, dict):
        payload = [payload]

    return TaskRowsAdapter.validate_python(payload)


def _select_task(tasks: list[Task], task_id: str | None) -> Task:
    if not tasks:
        raise ValueError("Task file is empty.")

    if task_id is None:
        if len(tasks) == 1:
            return tasks[0]
        task_ids = ", ".join(task.task_id for task in tasks)
        raise ValueError(f"Multiple tasks found. Pass --task-id. Available: {task_ids}")

    for task in tasks:
        if task.task_id == task_id:
            return task

    raise ValueError(f"Unknown task_id: {task_id}")


def _apply_profile_setup(profile_dir: Path, setup: ProfileSetup | None) -> None:
    apply_chromium_profile_file_setup(profile_dir, setup)


async def _collect_runtime_observations(
    context: BrowserContext,
    evaluation: Evaluation,
) -> dict[int, Observation]:
    observations: dict[int, Observation] = {}

    for idx, rule in enumerate(evaluation.rules):
        if not isinstance(rule, ChromiumRule):
            continue

        if rule.type == "active_url":
            observations[idx] = await _active_url_observation(context, rule)
            continue

        if rule.type == "open_tabs":
            observations[idx] = [page.url for page in context.pages]

    return observations


async def _active_url_observation(context: BrowserContext, rule: ChromiumRule) -> Observation:
    pages = list(context.pages)
    visible_page = await _visible_page(pages)
    if visible_page is not None:
        return visible_page.url

    matching_page = _matching_page(pages, rule)
    if matching_page is not None:
        return matching_page.url

    last_page = pages[-1] if pages else None
    return last_page.url if last_page is not None else None


async def _visible_page(pages: list[Page]) -> Page | None:
    for page in reversed(pages):
        try:
            visibility_state = await page.evaluate("document.visibilityState")
        except Exception:
            continue
        if visibility_state == "visible":
            return page
    return None


def _matching_page(pages: list[Page], rule: ChromiumRule) -> Page | None:
    for page in reversed(pages):
        if _value_matches(
            page.url,
            rule.value,
            match=rule.match,
            normalize_space=rule.normalize_space,
            case_sensitive=rule.case_sensitive,
        ):
            return page
    return None


def _evaluate_profile(
    evaluation: Evaluation,
    profile_dir: Path,
    runtime_observations: dict[int, Observation] | None = None,
) -> tuple[list[CheckResult], float]:
    observations: list[Observation] = []
    checks: list[CheckResult] = []

    for idx, rule in enumerate(evaluation.rules):
        if isinstance(rule, ChromiumRule):
            observed = _evaluate_chromium_rule(
                rule=rule,
                profile_dir=profile_dir,
                runtime_observations=runtime_observations,
                index=idx,
            )
            passed = _value_matches(
                observed,
                rule.value,
                match=rule.match,
                normalize_space=rule.normalize_space,
                case_sensitive=rule.case_sensitive,
            )
            observations.append(observed)
            checks.append(
                CheckResult(
                    index=idx,
                    mode=rule.mode,
                    rule_type=rule.type,
                    file=rule.file,
                    path=rule.path,
                    query=rule.query,
                    domain=rule.domain,
                    expected=rule.value,
                    observed=observed,
                    passed=passed,
                )
            )
            continue

        observations.append(None)
        checks.append(
            CheckResult(
                index=idx,
                mode=rule.mode,
                rule_type=None,
                expected=rule.value,
                observed=None,
                passed=False,
                note=_unsupported_rule_note(rule),
            )
        )

    return checks, float(evaluate_page_rules(evaluation, observations))


def _evaluate_chromium_rule(
    *,
    rule: ChromiumRule,
    profile_dir: Path,
    runtime_observations: dict[int, Observation] | None,
    index: int,
) -> Observation:
    if rule.type == "json_value":
        return evaluate_chromium_profile_rule(profile_dir, rule)

    if rule.type in {"active_url", "open_tabs"}:
        if runtime_observations is None:
            return None
        return runtime_observations.get(index)

    return evaluate_chromium_profile_rule(profile_dir, rule)


def _unsupported_rule_note(rule: object) -> str:
    if isinstance(rule, DomRule):
        return "manual_chromium_eval currently evaluates profile rules only, not DOM rules."
    if isinstance(rule, ConsoleRule):
        return "manual_chromium_eval currently evaluates profile rules only, not console rules."
    return "manual_chromium_eval does not support this rule type."


def _print_result(
    task: Task,
    profile_dir: Path,
    checks: list[CheckResult],
    reward: float,
) -> None:
    payload = {
        "task_id": task.task_id,
        "profile_dir": str(profile_dir),
        "reward": reward,
        "checks": [
            {
                "index": check.index,
                "mode": check.mode,
                "type": check.rule_type,
                "file": check.file,
                "path": check.path,
                "query": check.query,
                "domain": check.domain,
                "expected": check.expected,
                "observed": check.observed,
                "passed": check.passed,
                "note": check.note,
            }
            for check in checks
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _set_json_value(path: Path, dotted_path: str, value: Value) -> None:
    if path.exists():
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON profile file: {path}") from exc
    else:
        data = {}

    if not isinstance(data, dict):
        raise ValueError(f"Profile JSON root must be an object: {path}")

    current: dict[str, Any] = data
    keys = dotted_path.split(".")
    for key in keys[:-1]:
        child = current.get(key)
        if child is None:
            child = {}
            current[key] = child
        if not isinstance(child, dict):
            raise ValueError(f"Cannot set nested path through non-object key: {key}")
        current = child

    current[keys[-1]] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_profile_json_value(
    *,
    profile_dir: Path,
    relative_file: str,
    dotted_path: str,
) -> Observation:
    path = _safe_profile_path(profile_dir, relative_file)
    if path is None or not path.exists():
        return None

    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    current: Any = data
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]

    if isinstance(current, bool):
        return current
    if isinstance(current, str):
        return current
    if isinstance(current, int):
        return current
    if isinstance(current, float):
        return current
    return None


def _find_bookmark_bar_folder(profile_dir: Path, expected_name: str) -> Observation:
    data = _read_profile_json_file(profile_dir, "Default/Bookmarks")
    if not isinstance(data, dict):
        return None

    bookmark_bar = _bookmark_bar_root(data)
    if bookmark_bar is None:
        return None

    for child in bookmark_bar.get("children", []):
        if not isinstance(child, dict):
            continue
        if child.get("type") == "folder" and child.get("name") == expected_name:
            return expected_name
    return None


def _find_bookmark_bar_url(profile_dir: Path, expected_url: str) -> Observation:
    data = _read_profile_json_file(profile_dir, "Default/Bookmarks")
    if not isinstance(data, dict):
        return None

    bookmark_bar = _bookmark_bar_root(data)
    if bookmark_bar is None:
        return None

    for child in _walk_bookmark_nodes(bookmark_bar):
        if not isinstance(child, dict):
            continue
        if child.get("type") == "url" and child.get("url") == expected_url:
            return expected_url
    return None


def _read_profile_json_file(profile_dir: Path, relative_file: str) -> Any:
    path = _safe_profile_path(profile_dir, relative_file)
    if path is None or not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _bookmark_bar_root(data: dict[str, Any]) -> dict[str, Any] | None:
    roots = data.get("roots")
    if not isinstance(roots, dict):
        return None

    bookmark_bar = roots.get("bookmark_bar")
    return bookmark_bar if isinstance(bookmark_bar, dict) else None


def _walk_bookmark_nodes(node: dict[str, Any]):
    children = node.get("children", [])
    if not isinstance(children, list):
        return

    for child in children:
        yield child
        if isinstance(child, dict):
            yield from _walk_bookmark_nodes(child)


def _safe_profile_path(profile_dir: Path, relative_file: str) -> Path | None:
    profile_root = profile_dir.resolve()
    path = (profile_root / relative_file).resolve()
    if not path.is_relative_to(profile_root):
        return None
    return path


def _value_matches(
    actual: Observation,
    expected: Value,
    *,
    match: str,
    normalize_space: bool,
    case_sensitive: bool,
) -> bool:
    if isinstance(actual, list) or isinstance(expected, list):
        return _list_value_matches(
            actual,
            expected,
            match=match,
            normalize_space=normalize_space,
            case_sensitive=case_sensitive,
        )

    actual_text = "" if actual is None else str(actual)
    expected_text = str(expected)

    if normalize_space:
        actual_text = " ".join(actual_text.split())
        expected_text = " ".join(expected_text.split())

    if match == "exact":
        if not case_sensitive:
            actual_text = actual_text.casefold()
            expected_text = expected_text.casefold()
        return actual_text == expected_text

    if match == "contains":
        if not case_sensitive:
            actual_text = actual_text.casefold()
            expected_text = expected_text.casefold()
        return expected_text in actual_text

    if match == "regex":
        import re

        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(expected_text, actual_text, flags=flags) is not None

    return False


def _list_value_matches(
    actual: Observation,
    expected: Value,
    *,
    match: str,
    normalize_space: bool,
    case_sensitive: bool,
) -> bool:
    if not isinstance(actual, list) or not isinstance(expected, list):
        return False

    actual_values = [
        _normalize_match_text(value, normalize_space=normalize_space, case_sensitive=case_sensitive)
        for value in actual
    ]
    expected_values = [
        _normalize_match_text(value, normalize_space=normalize_space, case_sensitive=case_sensitive)
        for value in expected
    ]

    if match == "exact":
        return actual_values == expected_values

    if match == "contains":
        return all(value in actual_values for value in expected_values)

    if match == "regex":
        import re

        flags = 0 if case_sensitive else re.IGNORECASE
        return all(
            any(
                re.search(expected_pattern, actual_value, flags=flags)
                for actual_value in actual_values
            )
            for expected_pattern in expected_values
        )

    return False


def _normalize_match_text(
    value: str,
    *,
    normalize_space: bool,
    case_sensitive: bool,
) -> str:
    text = value
    if normalize_space:
        text = " ".join(text.split())
    if not case_sensitive:
        text = text.casefold()
    return text


if __name__ == "__main__":
    main()
