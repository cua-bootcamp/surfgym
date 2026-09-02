import asyncio
import math
from io import BytesIO
from itertools import groupby
from typing import Literal, cast

from PIL import Image
from playwright.async_api import Page
from pydantic import ValidationError
from surfgym_contracts.command import Command
from surfgym_contracts.protocol.artifact import ArtifactPayload, ArtifactSpec
from surfgym_contracts.task import (
    ConsoleCriteria,
    Criteria,
    DomCriteria,
    Hook,
    Observation,
    Value,
    Website,
)

from surfgym_runtime.wavepool.instance.error import InstanceError, InvalidCommand
from surfgym_runtime.wavepool.instance.session import (
    ContextManager,
    PageCursor,
    PageLayout,
    ScreenCursor,
)


class PlaywrightBrowserWorker:
    def __init__(
        self,
        *,
        contexts_per_instance: int,
        headed: bool = False,
        ignore_https_errors: bool = False,
    ) -> None:
        self.viewport_width = 1920
        self.viewport_height = 1080
        self.ctx_manager = ContextManager(
            contexts_per_instance=contexts_per_instance,
            vw=self.viewport_width,
            vh=self.viewport_height,
            headed=headed,
            ignore_https_errors=ignore_https_errors,
        )

    async def open(self) -> None:
        await self.ctx_manager.open()

    async def close(self) -> None:
        await self.ctx_manager.close()

    async def allocate(
        self,
        context_id: str,
        websites: list[Website],
        hooks: list[Hook],
    ):
        await self.ctx_manager.create(context_id, websites)
        ctx = self.ctx_manager.require_context(context_id)

        async def load_website(website: Website) -> None:
            page, _ = self.ctx_manager.require_page(ctx.context_id, website.website_id)
            response = await page.goto(website.url, wait_until="domcontentloaded")
            if response is not None and not 200 <= response.status < 300:
                retryable = response.status == 429 or 500 <= response.status < 600
                raise InstanceError(
                    f"Initial navigation failed with HTTP {response.status}: {website.url}",
                    response.status,
                    retryable=retryable,
                )
            ctx.entered_page_ids.add(website.website_id)

        navigation_results = await asyncio.gather(
            *(load_website(website) for website in websites),
            return_exceptions=True,
        )
        navigation_errors = [
            result for result in navigation_results if isinstance(result, BaseException)
        ]
        non_retryable_error = next(
            (
                error
                for error in navigation_errors
                if isinstance(error, InstanceError) and not error.retryable
            ),
            None,
        )
        if non_retryable_error is not None:
            raise non_retryable_error
        if navigation_errors:
            raise navigation_errors[0]

        await self._run_hooks(context_id, hooks, timing="after")

    async def release(self, context_id: str, hooks: list[Hook]):
        ctx = self.ctx_manager.require_context(context_id)
        async with ctx.operation_lock:
            if self.ctx_manager.require_context(context_id) is not ctx:
                raise InvalidCommand("context identity changed before release")

            # A Docker release hook is the acknowledgement that the fixture reset
            # was accepted. Preserve the browser context on failure so the Master
            # can retry this exact release instead of retrying a missing context.
            await self._run_hooks(context_id, hooks, timing="before", entered_only=True)
            await self.ctx_manager.delete(context_id)

    async def execute(self, context_id: str, command: Command):
        ctx = self.ctx_manager.require_context(context_id)

        def active_page() -> tuple[Page, PageLayout]:
            return self.ctx_manager.require_page(context_id, ctx.active_page_id)

        def focus_at(x: float, y: float) -> tuple[Page, PageCursor]:
            return self.ctx_manager.focus_page_at_screen_cursor(ctx, ScreenCursor(x, y))

        async def abort_cross_surface_drag() -> None:
            """Release the originating surface before rejecting a cross-surface drag."""
            if ctx.mouse_down_page_id is None:
                return

            page, _ = self.ctx_manager.require_page(context_id, ctx.mouse_down_page_id)
            try:
                await page.mouse.up()
            except Exception:
                # The command being rejected is still deterministic even if the
                # best-effort browser cleanup races with a page failure.
                pass
            finally:
                ctx.mouse_down_page_id = None

        match command.command:
            case "mouse_move":
                try:
                    page, cursor = focus_at(command.x, command.y)
                except InvalidCommand as error:
                    if error.message == "cannot drag across independent page surfaces":
                        await abort_cross_surface_drag()
                    raise
                await page.mouse.move(cursor.x, cursor.y)

            case "mouse_click":
                if command.x is None or command.y is None:
                    page, _ = active_page()
                    cursor = ctx.cursor
                else:
                    page, cursor = focus_at(command.x, command.y)
                option_value = await page.evaluate(
                    SAFE_CLICK_SCRIPT,
                    [cursor.x, cursor.y],
                )
                if option_value is not None:
                    await page.locator("select:focus").select_option(value=option_value)
                else:
                    await page.mouse.click(
                        cursor.x,
                        cursor.y,
                        delay=10,
                        button=command.button,
                        click_count=command.clickCount,
                    )

            case "mouse_down":
                page, _ = active_page()
                await page.mouse.down()
                ctx.mouse_down_page_id = ctx.active_page_id

            case "mouse_up":
                page, _ = active_page()
                await page.mouse.up()
                ctx.mouse_down_page_id = None

            case "mouse_wheel":
                page, _ = active_page()
                await page.mouse.wheel(command.dx, command.dy)

            case "drag_to":
                origin_page_id = ctx.mouse_down_page_id or ctx.active_page_id
                target_page_id, _, _ = self.ctx_manager.page_at_screen_cursor(
                    ctx,
                    ScreenCursor(command.x, command.y),
                )
                if target_page_id != origin_page_id:
                    await abort_cross_surface_drag()
                    raise InvalidCommand("cannot drag across independent page surfaces")
                page, cursor = focus_at(command.x, command.y)
                if ctx.mouse_down_page_id is None:
                    await page.mouse.down()
                await page.mouse.move(cursor.x, cursor.y, steps=20)
                await page.mouse.up()
                ctx.mouse_down_page_id = None

            case "typing":
                page, _ = active_page()
                await page.keyboard.type(command.text)

            case "key_down":
                page, _ = active_page()
                await page.keyboard.down(command.key)

            case "key_up":
                page, _ = active_page()
                await page.keyboard.up(command.key)

            case "key_press":
                page, _ = active_page()
                await page.keyboard.press(command.key)

            case "hot_key":
                page, _ = active_page()
                for key in command.keys:
                    await page.keyboard.down(key)
                for key in reversed(command.keys):
                    await page.keyboard.up(key)

            case "sleep":
                page, _ = active_page()
                await page.wait_for_timeout(command.duration_ms)

    async def screenshot(self, context_id: str) -> tuple[BytesIO, float, float]:
        ctx = self.ctx_manager.require_context(context_id)
        await asyncio.sleep(1)
        canvas = Image.new(
            "RGB",
            (self.viewport_width, self.viewport_height),
            color=(255, 255, 255),
        )

        for _, page_meta in ctx.pages.items():
            page, layout = page_meta
            screenshot_bytes = await page.screenshot()
            page_image = Image.open(BytesIO(screenshot_bytes)).convert("RGB")

            canvas.paste(page_image, (layout.x, layout.y))

        output = BytesIO()
        canvas.save(output, format="PNG")
        output.seek(0)

        _, layout = self.ctx_manager.require_page(ctx.context_id, ctx.active_page_id)
        screen_cursor = ctx.cursor.to_screen_cursor(layout)
        return output, screen_cursor.x, screen_cursor.y

    async def observe(self, context_id: str, criteria: list[Criteria], hooks: list[Hook]):
        await self._run_hooks(context_id, hooks, timing="before")

        observations: list[Observation] = [None] * len(criteria)
        console_critera: list[tuple[ConsoleCriteria, Page, int]] = []
        dom_criteria: list[tuple[DomCriteria, Page, int]] = []

        for idx, rule in enumerate(criteria):
            page, _ = self.ctx_manager.require_page(context_id, rule.website_id)
            match rule:
                case DomCriteria():
                    dom_criteria.append((rule, page, idx))
                case ConsoleCriteria():
                    console_critera.append((rule, page, idx))

        console_results, dom_results = await asyncio.gather(
            console_observation(console_critera),
            dom_observation(dom_criteria),
        )

        for obs, idx in console_results + dom_results:
            observations[idx] = obs

        await self._run_hooks(context_id, hooks, timing="after")
        return observations

    async def artifact(self, context_id: str, artifact: ArtifactSpec) -> ArtifactPayload:
        ctx = self.ctx_manager.require_context(context_id)
        async with ctx.operation_lock:
            if self.ctx_manager.require_context(context_id) is not ctx:
                raise InvalidCommand("context identity changed before artifact retrieval")
            if len(ctx.native_page_ids) != 1:
                raise InvalidCommand("artifact retrieval requires exactly one native surface")

            page, _ = self.ctx_manager.require_page(context_id, ctx.native_page_ids[0])
            result = await page.evaluate(
                """
                async (artifact) => {
                    const response = await fetch("/artifact", {
                        method: "POST",
                        credentials: "same-origin",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(artifact),
                    });
                    let payload;
                    try {
                        payload = await response.json();
                    } catch (_) {
                        throw new Error(
                            `artifact endpoint returned HTTP ${response.status} without JSON`
                        );
                    }
                    if (!response.ok) {
                        throw new Error(`artifact endpoint returned HTTP ${response.status}`);
                    }
                    return payload;
                }
                """,
                artifact.model_dump(mode="json"),
            )

            expected_keys = {
                "ok",
                "path",
                "mime_type",
                "sha256",
                "size",
                "encoding",
                "data",
            }
            if (
                not isinstance(result, dict)
                or set(result) != expected_keys
                or result.get("ok") is not True
            ):
                raise InvalidCommand("artifact endpoint returned an invalid success envelope")

            try:
                payload = ArtifactPayload.model_validate(
                    {key: value for key, value in result.items() if key != "ok"}
                )
            except ValidationError as exc:
                raise InvalidCommand("artifact endpoint returned an invalid payload") from exc

            if payload.path != artifact.path or payload.size > artifact.max_bytes:
                raise InvalidCommand("artifact response does not match the requested bounds")
            return payload

    async def _run_hooks(
        self,
        context_id: str,
        hooks: list[Hook],
        *,
        timing: Literal["before", "after"],
        entered_only: bool = False,
    ):
        selected_hooks = (hook for hook in hooks if hook.timing == timing)
        if entered_only:
            entered_page_ids = self.ctx_manager.require_context(context_id).entered_page_ids
            selected_hooks = (
                hook for hook in selected_hooks if hook.website_id in entered_page_ids
            )

        for website_id, website_hooks in groupby(
            selected_hooks,
            key=lambda hook: hook.website_id,
        ):
            page, _ = self.ctx_manager.require_page(context_id, website_id)
            scripts = [hook.script for hook in website_hooks]

            await page.evaluate(
                """
                async (scripts) => {
                    for (const script of scripts) {
                        await eval(script);
                    }
                }
                """,
                scripts,
            )


########################################
#           Helper Functions           #
########################################


async def _eval_console_observation(
    criteria: ConsoleCriteria,
    page: Page,
    idx: int,
) -> tuple[Observation, int]:
    try:
        observation = await page.evaluate(criteria.script)
    except Exception:
        observation = None

    return _coerce_playwright_observation(observation), idx


async def console_observation(
    criteria_and_page: list[tuple[ConsoleCriteria, Page, int]],
) -> list[tuple[Observation, int]]:
    results = await asyncio.gather(
        *(
            _eval_console_observation(criteria, page, idx)
            for criteria, page, idx in criteria_and_page
        )
    )

    return list(results)


async def dom_observation(
    criteria_and_page: list[tuple[DomCriteria, Page, int]],
) -> list[tuple[Observation, int]]:
    result: list[tuple[Observation, int]] = []

    page_groups: dict[Page, list[tuple[DomCriteria, int]]] = {}

    for criteria, page, idx in criteria_and_page:
        page_groups.setdefault(page, []).append((criteria, idx))

    for page, criteria_idx_arr in page_groups.items():
        rule_arr = [criteria for criteria, _ in criteria_idx_arr]
        idx_arr = [idx for _, idx in criteria_idx_arr]

        try:
            obs_arr = await page.evaluate(
                """
                (rules) => {
                    return Surfgym.getDomObservation(rules);
                }
                """,
                [rule.model_dump(mode="json") for rule in rule_arr],
            )
        except Exception:
            obs_arr = [None] * len(rule_arr)

        result.extend(
            (_coerce_playwright_observation(obs), idx) for obs, idx in zip(obs_arr, idx_arr)
        )

    return result


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

    if isinstance(value, list):
        list_result: list[Value] = []

        for item in cast(list[object], value):
            coerced_item = _coerce_playwright_observation(item)

            if item is not None and coerced_item is None:
                return None

            list_result.append(coerced_item)

        return list_result

    if isinstance(value, dict):
        dict_result: dict[str, Value] = {}

        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                return None

            coerced_item = _coerce_playwright_observation(item)

            if item is not None and coerced_item is None:
                return None

            dict_result[key] = coerced_item

        return dict_result

    return None


# Native <select> popups are not reliably handled by coordinate clicks in Playwright.
# Detect option clicks from screen position and fall back to select_option().
SAFE_CLICK_SCRIPT = """([x, y]) => {
    const active = document.activeElement;
    if (!active || active.tagName !== 'SELECT') return null;
    const rect = active.getBoundingClientRect();
    const opts = Array.from(active.options);
    if (!opts.length) return null;
    const relY = y - rect.bottom;
    if (relY < 0) return null;
    const optionHeight = rect.height > 0 ? rect.height : 22;
    const idx = Math.floor(relY / optionHeight);
    if (idx < 0 || idx >= opts.length) return null;
    return opts[idx].value;
}"""
