import asyncio
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, DefaultDict, Optional

from PIL import Image
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from surfgym_contracts.command import Command
from surfgym_contracts.protocol.upstream_to_gateway import ObservationResponse
from surfgym_contracts.task import (
    Action,
    ConsoleRule,
    DomRule,
    Observation,
    RuleBasedEvaluation,
    Website,
)
from typing_extensions import assert_never

from surfgym_runtime.support import instance_logger
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
    pages: dict[str, Page]
    page_layouts: dict[str, PageLayout]
    active_page_id: str | None
    controller: PlaywrightController
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closing: bool = False


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
    ) -> None:
        browser = self._require_browser()

        async with self._sessions_lock:
            if instance_id in self.sessions or instance_id in self._starting_sessions:
                raise CreateFailed(f"Instance id already exists: {instance_id}")

            if self._allocated_count() >= self.contexts_per_instance:
                raise InstanceNotIdle("No available context slot on this instance.")

            self._starting_sessions.add(instance_id)

        context: BrowserContext | None = None
        committed = False

        try:
            context_options: dict[str, Any] = {
                "viewport": {"width": self.viewport_width, "height": self.viewport_height},
                "ignore_https_errors": True,
            }

            username = os.getenv("SURFGYM_HTTP_AUTH_USERNAME")
            password = os.getenv("SURFGYM_HTTP_AUTH_PASSWORD")
            if username and password:
                context_options["http_credentials"] = {
                    "username": username,
                    "password": password,
                }
            elif username or password:
                instance_logger.warning(
                    "Ignoring incomplete HTTP Basic Auth credentials; set both "
                    "SURFGYM_HTTP_AUTH_USERNAME and SURFGYM_HTTP_AUTH_PASSWORD."
                )

            context = await browser.new_context(**context_options)
            state = ContextState(
                instance_id=instance_id,
                context=context,
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

    async def delete(self, instance_id: str) -> None:
        state = await self._mark_closing(instance_id)

        try:
            async with state.lock:
                for page in state.pages.values():
                    if not page.is_closed():
                        await page.close()
                await state.context.close()
        finally:
            async with self._sessions_lock:
                self.sessions.pop(instance_id, None)

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
                page = self._page_for_website(state, action.website_id, context="setup action")
                await page.evaluate(action.script)

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
        evaluation: RuleBasedEvaluation,
    ) -> ObservationResponse:
        rules = evaluation.rules
        observations: list[Observation] = [None] * len(rules)

        dom_groups: DefaultDict[str, list[tuple[int, DomRule]]] = defaultdict(list)
        console_groups: DefaultDict[str, list[tuple[int, ConsoleRule]]] = defaultdict(list)

        for idx, rule in enumerate(rules):
            match rule:
                case DomRule():
                    dom_groups[rule.website_id].append((idx, rule))
                case ConsoleRule():
                    console_groups[rule.website_id].append((idx, rule))

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
