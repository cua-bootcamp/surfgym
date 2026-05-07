from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEFAULT_BLOCK_PHRASES = (
    "비정상 서비스 접속으로 차단되었습니다",
    "서비스 접속이 차단되었습니다",
    "현재 접속하신 단말에서는 접속이 불가능합니다",
    "매크로 및 기타 유사 프로그램",
    "접속대기",
)


@dataclass
class BrowserSession:
    worker_id: int
    context: BrowserContext | None
    page: Page | None
    navigation_result: dict[str, Any]


def _load_websites_from_task_file(task_file: Path) -> list[str]:
    from src.components.task import TaskStore

    task_store = TaskStore.from_file(task_file)
    websites: set[str] = set()

    for task in task_store.values():
        for website in task.website:
            websites.add(website.url)

    return sorted(websites)


def _is_png(payload: bytes) -> bool:
    return payload.startswith(PNG_SIGNATURE) and len(payload) > len(PNG_SIGNATURE)


def _website_slug(website: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", website).strip("-").lower()
    digest = hashlib.sha1(website.encode("utf-8")).hexdigest()[:10]
    return f"{slug[:60] or 'website'}-{digest}"


async def capture_screenshot(
    page: Page,
    *,
    screenshot_dir: Path | None,
    website: str,
    phase: str,
    worker_id: int,
    repeat: int | None,
    timeout_ms: int,
) -> tuple[bool, str | None]:
    screenshot = await page.screenshot(timeout=timeout_ms)
    screenshot_path = None

    if screenshot_dir is not None:
        filename = f"{phase}-worker-{worker_id}"
        if repeat is not None:
            filename += f"-repeat-{repeat}"
        screenshot_path = screenshot_dir / _website_slug(website) / f"{filename}.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(screenshot)

    return _is_png(screenshot), str(screenshot_path) if screenshot_path is not None else None


async def collect_block_phrases(page: Page) -> list[str]:
    body_text = await page.text_content("body") or ""
    return [phrase for phrase in DEFAULT_BLOCK_PHRASES if phrase in body_text]


async def launch_browsers(playwright: Playwright, *, concurrency: int) -> list[Browser]:
    if concurrency < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency}")

    results = await asyncio.gather(
        *[playwright.chromium.launch(headless=True) for _ in range(concurrency)],
        return_exceptions=True,
    )

    browsers: list[Browser] = []
    errors: list[str] = []

    for worker_id, result in enumerate(results, start=1):
        if isinstance(result, BaseException):
            errors.append(f"worker {worker_id}: {type(result).__name__}: {result}")
        else:
            browsers.append(result)

    if errors:
        await close_browsers(browsers)
        raise RuntimeError("failed to launch browser(s): " + "; ".join(errors))

    return browsers


async def close_browsers(browsers: list[Browser]) -> None:
    await asyncio.gather(
        *[browser.close() for browser in browsers],
        return_exceptions=True,
    )


async def close_sessions(sessions: list[BrowserSession]) -> None:
    await asyncio.gather(
        *[session.context.close() for session in sessions if session.context is not None],
        return_exceptions=True,
    )


async def navigate_browser(
    browser: Browser,
    website: str,
    *,
    worker_id: int,
    timeout_ms: int,
    screenshot_dir: Path | None,
) -> BrowserSession:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    started = time.perf_counter()
    context: BrowserContext | None = None
    page: Page | None = None
    keep_page = False

    result: dict[str, Any] = {
        "url": website,
        "worker_id": worker_id,
        "phase": "navigate",
        "ok": False,
        "status": "unknown",
        "http_status": None,
        "final_url": None,
        "title": None,
        "blocked_phrases": [],
    }

    try:
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        response = await page.goto(
            website,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )

        result["http_status"] = response.status if response else None
        result["final_url"] = page.url
        result["title"] = await page.title()
        result["blocked_phrases"] = await collect_block_phrases(page)
        screenshot_ok, screenshot_path = await capture_screenshot(
            page,
            screenshot_dir=screenshot_dir,
            website=website,
            phase="navigate",
            worker_id=worker_id,
            repeat=None,
            timeout_ms=timeout_ms,
        )
        result["screenshot_ok"] = screenshot_ok
        if screenshot_path is not None:
            result["screenshot_path"] = screenshot_path

        if result["blocked_phrases"]:
            result["status"] = "blocked_after_navigation"
        elif result["http_status"] is not None and int(result["http_status"]) >= 400:
            result["status"] = "http_error"
        elif not screenshot_ok:
            result["status"] = "invalid_screenshot"
        else:
            result["ok"] = True
            result["status"] = "ok"
            keep_page = True

    except PlaywrightTimeoutError as exc:
        result["status"] = "navigation_timeout"
        result["error"] = str(exc).splitlines()[0]
        result["final_url"] = page.url if page else None

    except PlaywrightError as exc:
        result["status"] = "navigation_playwright_error"
        result["error"] = str(exc).splitlines()[0]
        result["final_url"] = page.url if page else None

    except Exception as exc:
        result["status"] = "navigation_error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["final_url"] = page.url if page else None

    finally:
        result["duration_sec"] = round(time.perf_counter() - started, 3)

    if not keep_page and context is not None:
        await context.close()
        context = None
        page = None

    return BrowserSession(
        worker_id=worker_id,
        context=context,
        page=page,
        navigation_result=result,
    )


async def run_action_sequence_on_page(
    session: BrowserSession,
    *,
    repeat: int,
    timeout_ms: int,
    screenshot_dir: Path | None,
) -> dict[str, Any]:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    started = time.perf_counter()
    page = session.page

    result: dict[str, Any] = {
        "url": session.navigation_result["url"],
        "worker_id": session.worker_id,
        "phase": "action",
        "repeat": repeat,
        "ok": False,
        "status": "unknown",
        "http_status": session.navigation_result.get("http_status"),
        "final_url": None,
        "title": None,
        "blocked_phrases": [],
    }

    if page is None:
        result["status"] = "missing_page"
        result["duration_sec"] = round(time.perf_counter() - started, 3)
        return result

    try:
        await page.mouse.move(300, 300)
        await page.mouse.wheel(0, 500)
        await page.wait_for_timeout(1000)

        result["final_url"] = page.url
        result["title"] = await page.title()
        result["blocked_phrases"] = await collect_block_phrases(page)

        if result["blocked_phrases"]:
            result["status"] = "blocked_after_action"
            return result

        screenshot_ok, screenshot_path = await capture_screenshot(
            page,
            screenshot_dir=screenshot_dir,
            website=result["url"],
            phase="action",
            worker_id=session.worker_id,
            repeat=repeat,
            timeout_ms=timeout_ms,
        )
        result["screenshot_ok"] = screenshot_ok
        if screenshot_path is not None:
            result["screenshot_path"] = screenshot_path

        if not screenshot_ok:
            result["status"] = "invalid_screenshot"
            return result

        result["ok"] = True
        result["status"] = "ok"
        return result

    except PlaywrightTimeoutError as exc:
        result["status"] = "action_timeout"
        result["error"] = str(exc).splitlines()[0]
        result["final_url"] = page.url
        return result

    except PlaywrightError as exc:
        result["status"] = "action_playwright_error"
        result["error"] = str(exc).splitlines()[0]
        result["final_url"] = page.url
        return result

    except Exception as exc:
        result["status"] = "action_error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["final_url"] = page.url
        return result

    finally:
        result["duration_sec"] = round(time.perf_counter() - started, 3)


async def run_playwright_block_check(
    websites: list[str],
    *,
    repeats: int,
    concurrency: int,
    timeout_ms: int,
    screenshot_dir: Path | None,
) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    rows: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        for website in websites:
            browsers = await launch_browsers(playwright, concurrency=concurrency)
            sessions: list[BrowserSession] = []

            try:
                sessions = await asyncio.gather(
                    *[
                        navigate_browser(
                            browser,
                            website,
                            worker_id=worker_id,
                            timeout_ms=timeout_ms,
                            screenshot_dir=screenshot_dir,
                        )
                        for worker_id, browser in enumerate(browsers, start=1)
                    ]
                )
                rows.extend(session.navigation_result for session in sessions)

                active_sessions = [session for session in sessions if session.page is not None]
                for repeat in range(1, repeats + 1):
                    rows.extend(
                        await asyncio.gather(
                            *[
                                run_action_sequence_on_page(
                                    session,
                                    repeat=repeat,
                                    timeout_ms=timeout_ms,
                                    screenshot_dir=screenshot_dir,
                                )
                                for session in active_sessions
                            ]
                        )
                    )

            finally:
                await close_sessions(sessions)
                await close_browsers(browsers)

    return build_report(rows)


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_url[row["url"]].append(row)

    websites: list[object] = []
    for url, url_rows in by_url.items():
        status_counts = Counter(row["status"] for row in url_rows)
        navigate_rows = [row for row in url_rows if row["phase"] == "navigate"]
        action_rows = [row for row in url_rows if row["phase"] == "action"]
        blocked = sum(1 for row in url_rows if str(row["status"]).startswith("blocked"))
        screenshot_count = sum(1 for row in url_rows if row.get("screenshot_path"))

        websites.append(
            {
                "url": url,
                "ok": sum(1 for row in url_rows if row["ok"]),
                "total": len(url_rows),
                "blocked": blocked,
                "navigate_ok": sum(1 for row in navigate_rows if row["ok"]),
                "navigate_total": len(navigate_rows),
                "action_ok": sum(1 for row in action_rows if row["ok"]),
                "action_total": len(action_rows),
                "screenshots": screenshot_count,
                "statuses": dict(status_counts),
            }
        )

    return {"websites": websites}


def print_report(report: dict[str, Any]) -> None:
    for item in report["websites"]:
        print()
        print(f"url: {item['url']}")
        print(f"ok: {item['ok']}/{item['total']}")
        print(f"blocked: {item['blocked']}")
        print(f"navigate: {item['navigate_ok']}/{item['navigate_total']}")
        print(f"action: {item['action_ok']}/{item['action_total']}")
        print(f"screenshots: {item['screenshots']}")
        print(f"statuses: {item['statuses']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether websites from a SurfGym task file are blocked under concurrent Playwright access."
    )
    parser.add_argument("task_file", type=Path)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--screenshot-dir", type=Path, default=Path("/"))
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def _resolve_screenshot_dir(path: Path) -> Path | None:
    if path.is_absolute():
        path = path.relative_to(path.anchor)

    return ROOT_DIR / path


def main() -> int:
    args = parse_args()
    websites = _load_websites_from_task_file(args.task_file)

    screenshot_dir = _resolve_screenshot_dir(args.screenshot_dir)

    report = asyncio.run(
        run_playwright_block_check(
            websites,
            repeats=args.repeats,
            concurrency=args.concurrency,
            timeout_ms=args.timeout_ms,
            screenshot_dir=screenshot_dir,
        )
    )
    print_report(report)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print(f"json_out: {args.json_out}")

    has_failure = any(item["ok"] != item["total"] for item in report["websites"])
    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
