import asyncio
import json
import math
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, DefaultDict, Optional

from PIL import Image
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from surfgym_contracts.command import Command
from surfgym_contracts.protocol.upstream_to_gateway import ObservationResponse
from surfgym_contracts.task import (
    Action,
    ChromiumRule,
    ConsoleRule,
    DomRule,
    Evaluation,
    Observation,
    ProfileSetup,
    Website,
)
from typing_extensions import assert_never

from surfgym_runtime.support import instance_logger
from surfgym_runtime.support.chromium_profile import (
    apply_chromium_profile_file_setup,
    apply_chromium_runtime_profile_setup,
    evaluate_chromium_profile_rule,
    profile_setup_requires_persistent_context,
)
from surfgym_runtime.wavepool.instance.error import (
    CreateFailed,
    InstanceError,
    InstanceNotIdle,
    InvalidCommand,
    InvalidInstanceId,
    UnexpectedError,
)
from surfgym_runtime.wavepool.instance.transport import (
    PageCursor,
    PageLayout,
    PlaywrightController,
    ScreenCursor,
)


@dataclass
class ContextState:
    instance_id: str
    context: BrowserContext
    profile_dir: Path | None
    pages: dict[str, Page]
    page_layouts: dict[str, PageLayout]
    active_page_id: str | None
    controller: PlaywrightController
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closing: bool = False
    context_closed: bool = False


class PlaywrightBrowserWorker:
    def __init__(self, *, contexts_per_instance: int = 1) -> None:
        if contexts_per_instance < 1:
            raise ValueError("contexts_per_instance must be >= 1")

        self.viewport_width = 1920
        self.viewport_height = 1080
        self.contexts_per_instance = contexts_per_instance

        self.p: Playwright | None = None
        self.browser: Browser | None = None

        self.sessions: dict[str, ContextState] = {}
        self._starting_sessions: set[str] = set()
        self._sessions_lock = asyncio.Lock()

    async def open(self) -> None:
        if self.p is not None and self.browser is not None:
            return

        if self.p is not None or self.browser is not None:
            raise UnexpectedError("Inconsistent Playwright browser lifecycle state")

        try:
            self.p = await async_playwright().start()
            self.browser = await self.p.chromium.launch()
        except Exception:
            if self.browser is not None:
                await self.browser.close()
                self.browser = None
            if self.p is not None:
                await self.p.stop()
                self.p = None
            raise

    async def close(self) -> None:
        await self.delete_all()

        if self.browser is not None:
            await self.browser.close()
            self.browser = None

        if self.p is not None:
            await self.p.stop()
            self.p = None

    async def has_capacity(self) -> bool:
        async with self._sessions_lock:
            return self._allocated_count() < self.contexts_per_instance

    async def idle(self) -> bool:
        async with self._sessions_lock:
            return self._allocated_count() == 0

    async def create(
        self,
        instance_id: str,
        websites: list[Website],
        setup: Optional[list[Action]],
        profile_setup: Optional[ProfileSetup],
    ) -> None:
        browser = self._require_browser()

        async with self._sessions_lock:
            if instance_id in self.sessions or instance_id in self._starting_sessions:
                raise CreateFailed(f"Instance id already exists: {instance_id}")

            if self._allocated_count() >= self.contexts_per_instance:
                raise InstanceNotIdle("No available context slot on this instance.")

            self._starting_sessions.add(instance_id)

        context: BrowserContext | None = None
        profile_dir: Path | None = None
        committed = False

        try:
            if _requires_persistent_profile(websites, profile_setup):
                profile_dir = Path(tempfile.mkdtemp(prefix=f"surfgym-{instance_id}-"))
                apply_chromium_profile_file_setup(profile_dir, profile_setup)
                context = await self._require_playwright().chromium.launch_persistent_context(
                    profile_dir,
                    viewport={"width": self.viewport_width, "height": self.viewport_height},
                )
            else:
                context = await browser.new_context(
                    viewport={"width": self.viewport_width, "height": self.viewport_height}
                )

            await apply_chromium_runtime_profile_setup(context, profile_setup)
            state = ContextState(
                instance_id=instance_id,
                context=context,
                profile_dir=profile_dir,
                pages={},
                page_layouts={},
                active_page_id=None,
                controller=PlaywrightController(),
            )

            await self._initialize_context(state, websites, setup)

            async with self._sessions_lock:
                self._starting_sessions.discard(instance_id)
                self.sessions[instance_id] = state
                committed = True
        except InstanceNotIdle:
            raise
        except Exception as exc:
            raise CreateFailed(
                f"Playwright context creation failed: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            if not committed:
                async with self._sessions_lock:
                    self._starting_sessions.discard(instance_id)

                if context is not None:
                    try:
                        await context.close()
                    except Exception:
                        instance_logger.exception(
                            "Failed to clean up partially created Playwright context"
                        )
                if profile_dir is not None:
                    shutil.rmtree(profile_dir, ignore_errors=True)

    async def delete(self, instance_id: str) -> None:
        state = await self._mark_closing(instance_id)

        try:
            async with state.lock:
                await self._close_context_state(state)
        finally:
            async with self._sessions_lock:
                self.sessions.pop(instance_id, None)
            if state.profile_dir is not None:
                shutil.rmtree(state.profile_dir, ignore_errors=True)

    async def delete_all(self) -> None:
        async with self._sessions_lock:
            instance_ids = list(self.sessions)

        for instance_id in instance_ids:
            try:
                await self.delete(instance_id)
            except InvalidInstanceId:
                pass
            except Exception:
                instance_logger.exception("Failed to delete Playwright context: %s", instance_id)

    async def screenshot(self, instance_id: str) -> tuple[BytesIO, float, float]:
        state = await self._get_state(instance_id)

        async with state.lock:
            return await self._screenshot_state(state)

    async def execute(self, instance_id: str, command: Command):
        state = await self._get_state(instance_id)

        async with state.lock:
            return await self._execute_in_state(state, command)

    async def _initialize_context(
        self,
        state: ContextState,
        websites: list[Website],
        setup: Optional[list[Action]],
    ) -> None:
        layouts = _build_page_layouts(
            page_count=len(websites),
            total_width=self.viewport_width,
            total_height=self.viewport_height,
        )

        for website, layout in zip(websites, layouts):
            page = await state.context.new_page()
            await state.controller.on_new_page(page, layout)
            await state.controller.visit_page(page, website.url)

            state.pages[website.website_id] = page
            state.page_layouts[website.website_id] = layout
            if state.active_page_id is None:
                state.active_page_id = website.website_id

        if setup:
            for action in setup:
                if action.mode == "playwright":
                    await self._run_playwright_setup_action(state, action.script)
                    continue

                page = self._page_for_website(state, action.website_id, context="setup action")
                await page.evaluate(action.script)

    async def _run_playwright_setup_action(self, state: ContextState, script: str) -> None:
        if script == "close_last_tab":
            pages = list(state.context.pages)
            if not pages:
                return

            page = pages[-1]
            await page.close()

            for website_id, tracked_page in list(state.pages.items()):
                if tracked_page == page:
                    state.pages.pop(website_id, None)
                    state.page_layouts.pop(website_id, None)
                    if state.active_page_id == website_id:
                        state.active_page_id = next(iter(state.pages), None)

            remaining_pages = [
                remaining for remaining in state.context.pages if not remaining.is_closed()
            ]
            if remaining_pages:
                await remaining_pages[-1].bring_to_front()
            return

        raise InvalidCommand(f"Unsupported Playwright setup action: {script}")

    async def _screenshot_state(self, state: ContextState) -> tuple[BytesIO, float, float]:
        try:
            await asyncio.sleep(1)
            canvas = Image.new(
                "RGB",
                (self.viewport_width, self.viewport_height),
                color=(255, 255, 255),
            )

            for website_id, page in state.pages.items():
                layout = state.page_layouts[website_id]

                screenshot_bytes = await state.controller.get_screenshot(page)
                page_image = Image.open(BytesIO(screenshot_bytes)).convert("RGB")

                canvas.paste(page_image, (layout.x, layout.y))

            output = BytesIO()
            canvas.save(output, format="PNG")
            output.seek(0)

            screen_cursor = self._page_to_screen_cursor(state)
            return output, screen_cursor.x, screen_cursor.y
        except InstanceError:
            raise
        except Exception as exc:
            raise UnexpectedError(f"Screenshot failed: {type(exc).__name__}: {exc}") from exc

    async def _execute_in_state(self, state: ContextState, command: Command):
        try:
            page = self._active_page(state)

            match command.command:
                case "mouse_move":
                    page_cursor = self._screen_to_page_cursor(state, command.x, command.y)
                    page = self._active_page(state)
                    return await state.controller.hover_coords(page, page_cursor)

                case "mouse_click":
                    page_cursor = self._screen_to_page_cursor(state, command.x, command.y)
                    page = self._active_page(state)
                    return await state.controller.click_coords(
                        page,
                        page_cursor,
                        command.button,
                        click_count=command.clickCount,
                    )

                case "mouse_down":
                    return await state.controller.mouse_down(page)

                case "mouse_up":
                    return await state.controller.mouse_up(page)

                case "mouse_wheel":
                    return await state.controller.scroll_pointer(page, command.dx, command.dy)

                case "drag_to":
                    page_cursor = self._screen_to_page_cursor(state, command.x, command.y)
                    page = self._active_page(state)
                    return await state.controller.drag_to(page, page_cursor)

                case "typing":
                    return await state.controller.keyboard_type(page, command.text)

                case "key_down":
                    return await state.controller.key_down(page, command.key)

                case "key_up":
                    return await state.controller.key_up(page, command.key)

                case "key_press":
                    return await state.controller.key_press(page, command.key)

                case "hot_key":
                    return await state.controller.hotkey_press(page, command.keys)

                case "observe":
                    return await self._get_observation(state, command.evaluation)

                case "sleep":
                    return await state.controller.sleep(page, command.duration_ms)

                case "command":
                    for action in command.actions:
                        page = self._page_for_website(
                            state,
                            action.website_id,
                            context="command action",
                        )
                        await page.evaluate(action.script)
                    return None

                case _ as unreachable:
                    assert_never(unreachable)

        except InstanceError:
            raise
        except Exception as exc:
            raise UnexpectedError(
                f"Command execution failed: command={command.command} "
                f"error={type(exc).__name__}: {exc}"
            ) from exc

    async def _get_observation(
        self,
        state: ContextState,
        evaluation: Evaluation,
    ) -> ObservationResponse:
        rules = evaluation.rules
        observations: list[Observation] = [None] * len(rules)

        dom_groups: DefaultDict[str, list[tuple[int, DomRule]]] = defaultdict(list)
        console_groups: DefaultDict[str, list[tuple[int, ConsoleRule]]] = defaultdict(list)
        chromium_rules: list[tuple[int, ChromiumRule]] = []

        for idx, rule in enumerate(rules):
            match rule:
                case DomRule():
                    dom_groups[rule.website_id].append((idx, rule))
                case ConsoleRule():
                    console_groups[rule.website_id].append((idx, rule))
                case ChromiumRule():
                    chromium_rules.append((idx, rule))

        for website_id, idx_rules in dom_groups.items():
            page = self._page_for_website(state, website_id, context="DOM observation")
            idx_arr = [idx for idx, _ in idx_rules]
            rule_arr = [rule for _, rule in idx_rules]

            obs_arr = await state.controller.get_dom_observation(
                page=page,
                dom_rules=rule_arr,
            )

            for original_idx, obs in zip(idx_arr, obs_arr):
                observations[original_idx] = _coerce_playwright_observation(obs)

        for website_id, idx_rules in console_groups.items():
            page = self._page_for_website(state, website_id, context="console observation")
            idx_arr = [idx for idx, _ in idx_rules]
            rule_arr = [rule for _, rule in idx_rules]

            obs_arr = await state.controller.get_console_observation(
                page=page,
                console_rules=rule_arr,
            )

            for original_idx, obs in zip(idx_arr, obs_arr):
                observations[original_idx] = _coerce_playwright_observation(obs)

        profile_chromium_rules: list[tuple[int, ChromiumRule]] = []
        for original_idx, rule in chromium_rules:
            if rule.type == "active_url":
                observations[original_idx] = await _active_url_observation(state.context, rule)
                continue

            if rule.type == "open_tabs":
                observations[original_idx] = [page.url for page in state.context.pages]
                continue

            profile_chromium_rules.append((original_idx, rule))

        if profile_chromium_rules:
            await self._close_context_state(state)

            for original_idx, rule in profile_chromium_rules:
                observations[original_idx] = evaluate_chromium_profile_rule(
                    profile_dir=state.profile_dir,
                    rule=rule,
                )

        return ObservationResponse(observation=observations)

    async def _get_state(self, instance_id: str) -> ContextState:
        async with self._sessions_lock:
            state = self.sessions.get(instance_id)

            if state is None or state.closing:
                raise InvalidInstanceId(f"Instance id {instance_id} is not running on this server.")

            return state

    async def _mark_closing(self, instance_id: str) -> ContextState:
        async with self._sessions_lock:
            state = self.sessions.get(instance_id)

            if state is None:
                raise InvalidInstanceId(f"Instance id {instance_id} is not running on this server.")

            state.closing = True
            return state

    def _require_browser(self) -> Browser:
        if self.browser is None:
            raise CreateFailed("Playwright browser is not open")
        return self.browser

    def _require_playwright(self) -> Playwright:
        if self.p is None:
            raise CreateFailed("Playwright is not open")
        return self.p

    async def _close_context_state(self, state: ContextState) -> None:
        if state.context_closed:
            return

        for page in state.pages.values():
            if not page.is_closed():
                await page.close()
        await state.context.close()
        state.context_closed = True

    def _allocated_count(self) -> int:
        return len(self.sessions) + len(self._starting_sessions)

    def _screen_to_page_cursor(
        self,
        state: ContextState,
        x: float | None,
        y: float | None,
    ) -> PageCursor:
        if x is None or y is None:
            return state.controller.cursor

        for website_id, layout in state.page_layouts.items():
            if layout.x <= x < layout.x + layout.width and layout.y <= y < layout.y + layout.height:
                if state.active_page_id != website_id:
                    state.active_page_id = website_id
                return PageCursor(x - layout.x, y - layout.y)

        raise RuntimeError(f"screen cursor is outside page layouts: ({x}, {y})")

    def _page_to_screen_cursor(self, state: ContextState) -> ScreenCursor:
        page_id = state.active_page_id
        if page_id is None:
            return ScreenCursor(0.0, 0.0)

        layout = state.page_layouts.get(page_id)
        if layout is None:
            return ScreenCursor(0.0, 0.0)

        return ScreenCursor(
            layout.x + state.controller.cursor.x,
            layout.y + state.controller.cursor.y,
        )

    def _active_page(self, state: ContextState) -> Page:
        page_id = state.active_page_id
        if page_id is None:
            raise UnexpectedError("active_page_id is not initialized")

        return self._page_for_website(state, page_id, context="active page")

    def _page_for_website(self, state: ContextState, website_id: str, *, context: str) -> Page:
        try:
            return state.pages[website_id]
        except KeyError as exc:
            raise InvalidCommand(f"{context} references unknown website_id: {website_id}") from exc


# Temporary compatibility name. Prefer importing PlaywrightBrowserWorker from server.py.
PlaywrightInstance = PlaywrightBrowserWorker


########################################
#           Helper Functions           #
########################################


def _build_page_layouts(
    *,
    page_count: int,
    total_width: int,
    total_height: int,
) -> list[PageLayout]:
    half_width = total_width // 2
    half_height = total_height // 2

    if page_count == 1:
        return [
            PageLayout(x=0, y=0, width=total_width, height=total_height),
        ]

    if page_count == 2:
        return [
            PageLayout(x=0, y=0, width=half_width, height=total_height),
            PageLayout(x=half_width, y=0, width=half_width, height=total_height),
        ]

    if page_count == 3:
        return [
            PageLayout(x=0, y=0, width=half_width, height=total_height),
            PageLayout(x=half_width, y=0, width=half_width, height=half_height),
            PageLayout(
                x=half_width,
                y=half_height,
                width=half_width,
                height=half_height,
            ),
        ]

    return [
        PageLayout(x=0, y=0, width=half_width, height=half_height),
        PageLayout(x=half_width, y=0, width=half_width, height=half_height),
        PageLayout(x=0, y=half_height, width=half_width, height=half_height),
        PageLayout(
            x=half_width,
            y=half_height,
            width=half_width,
            height=half_height,
        ),
    ]


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


def _requires_persistent_profile(
    websites: list[Website],
    profile_setup: ProfileSetup | None,
) -> bool:
    return any(website.url.startswith("chrome://") for website in websites) or (
        profile_setup_requires_persistent_context(profile_setup)
    )


def _value_matches(
    actual: Observation,
    expected: object,
    *,
    match: str,
    normalize_space: bool,
    case_sensitive: bool,
) -> bool:
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
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(expected_text, actual_text, flags=flags) is not None

    return False


def _read_profile_json_value(
    *,
    profile_dir: Path | None,
    relative_file: str,
    dotted_path: str,
) -> Observation:
    if profile_dir is None:
        return None

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

    return _coerce_playwright_observation(current)


def _safe_profile_path(profile_dir: Path, relative_file: str) -> Path | None:
    profile_root = profile_dir.resolve()
    path = (profile_root / relative_file).resolve()

    if not path.is_relative_to(profile_root):
        return None

    return path


def _coerce_playwright_observation(value: object) -> Observation:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return value

    return None
