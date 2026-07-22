import asyncio
import math
from io import BytesIO
from typing import cast

from PIL import Image
from playwright.async_api import Page
from surfgym_contracts.command import Command
from surfgym_contracts.task import (
    ConsoleCriteria,
    Criteria,
    DomCriteria,
    Hook,
    Observation,
    Value,
    Website,
)

from surfgym_runtime.wavepool.instance.session import ContextManager, ScreenCursor


class PlaywrightBrowserWorker:
    def __init__(self, *, contexts_per_instance: int, DEV_MODE: bool) -> None:
        self.viewport_width = 1920
        self.viewport_height = 1080
        self.ctx_manager = ContextManager(
            contexts_per_instance=contexts_per_instance,
            vw=self.viewport_width,
            vh=self.viewport_height,
        )

        self.DEV_MODE = DEV_MODE

    async def open(self) -> None:
        await self.ctx_manager.open()

    async def close(self) -> None:
        await self.ctx_manager.close()

    async def allocate(
        self,
        context_id: str,
        websites: list[Website],
        allocate_hooks: list[Hook],
    ):
        await self.ctx_manager.create(context_id, websites)
        ctx = self.ctx_manager.require_context(context_id)

        after_hooks: dict[str, list[Hook]] = {}

        for hook in allocate_hooks:
            if hook.timing == "after":
                after_hooks.setdefault(hook.website_id, []).append(hook)

        async def load_website(website: Website) -> None:
            page, _ = self.ctx_manager.require_page(ctx.context_id, website.website_id)
            await page.goto(website.url, wait_until="domcontentloaded")

            hooks = after_hooks.get(website.website_id)
            if hooks is not None:
                for hook in hooks:
                    await page.evaluate(hook.script)

        await asyncio.gather(*(load_website(website) for website in websites))

    async def release(self, context_id: str):
        await self.ctx_manager.delete(context_id)

    async def execute(self, context_id: str, command: Command):
        ctx = self.ctx_manager.require_context(context_id)
        page, layout = self.ctx_manager.require_page(context_id, ctx.active_page_id)

        match command.command:
            case "mouse_move":
                cursor = ScreenCursor(command.x, command.y).to_page_cursor(layout)
                await page.mouse.move(cursor.x, cursor.y)
                ctx.cursor = cursor

            case "mouse_click":
                cursor = (
                    ctx.cursor
                    if command.x is None or command.y is None
                    else ScreenCursor(command.x, command.y).to_page_cursor(layout)
                )
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
                ctx.cursor = cursor

            case "mouse_down":
                await page.mouse.down()

            case "mouse_up":
                await page.mouse.up()

            case "mouse_wheel":
                await page.mouse.wheel(command.dx, command.dy)

            case "drag_to":
                cursor = ScreenCursor(command.x, command.y).to_page_cursor(layout)
                await page.mouse.down()
                await page.mouse.move(cursor.x, cursor.y, steps=20)
                await page.mouse.up()
                ctx.cursor = cursor

            case "typing":
                await page.keyboard.type(command.text)

            case "key_down":
                await page.keyboard.down(command.key)

            case "key_up":
                await page.keyboard.up(command.key)

            case "key_press":
                await page.keyboard.press(command.key)

            case "hot_key":
                for key in command.keys:
                    await page.keyboard.down(key)
                for key in reversed(command.keys):
                    await page.keyboard.up(key)

            case "sleep":
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

    async def observe(self, context_id: str, criteria: list[Criteria], observe_hooks: list[Hook]):
        if self.DEV_MODE:

            async def run_before_hook(hook: Hook) -> None:
                page, _ = self.ctx_manager.require_page(context_id, hook.website_id)
                await page.evaluate(hook.script)

            await asyncio.gather(
                *(run_before_hook(hook) for hook in observe_hooks if hook.timing == "before")
            )

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

        async def run_after_hook(hook: Hook) -> None:
            page, _ = self.ctx_manager.require_page(context_id, hook.website_id)
            await page.evaluate(hook.script)

        await asyncio.gather(
            *(run_after_hook(hook) for hook in observe_hooks if hook.timing == "after")
        )

        return observations


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

            if coerced_item is None:
                return None

            list_result.append(coerced_item)

        return list_result

    if isinstance(value, dict):
        dict_result: dict[str, Value] = {}

        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                return None

            coerced_item = _coerce_playwright_observation(item)

            if coerced_item is None:
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
