import asyncio
import math
import secrets
import re
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from io import BytesIO
from itertools import groupby
from typing import Literal, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
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
from surfgym_runtime.wavepool.bindings import web_cleanup_cookie


DEFAULT_BINDING_CLEANUP_HORIZON_SECONDS = 720.0
DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS = 360.0
DEFAULT_BINDING_CLEANUP_RETRY_INTERVAL_SECONDS = 2.0


@dataclass(frozen=True)
class NativeBinding:
    context_id: str
    website_id: str
    origin: str
    session_id: str | None
    app: str | None
    cleanup_capability: str | None = None


@dataclass(frozen=True)
class WebBinding:
    context_id: str
    website_id: str
    origin: str
    cookie_name: str
    reset_path: str
    cookie_value: str


class PlaywrightBrowserWorker:
    def __init__(
        self,
        *,
        contexts_per_instance: int,
        headed: bool = False,
        ignore_https_errors: bool = False,
        binding_cleanup_horizon_seconds: float = DEFAULT_BINDING_CLEANUP_HORIZON_SECONDS,
        binding_cleanup_request_timeout_seconds: float = DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS,
        binding_cleanup_retry_interval_seconds: float = DEFAULT_BINDING_CLEANUP_RETRY_INTERVAL_SECONDS,
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
        self._native_bindings: dict[str, NativeBinding] = {}
        self._web_bindings: dict[str, dict[str, WebBinding]] = {}
        self.binding_cleanup_horizon_seconds = binding_cleanup_horizon_seconds
        self.binding_cleanup_request_timeout_seconds = binding_cleanup_request_timeout_seconds
        self.binding_cleanup_retry_interval_seconds = binding_cleanup_retry_interval_seconds

    async def open(self) -> None:
        await self.ctx_manager.open()

    async def close(self) -> None:
        await self.ctx_manager.close()

    @asynccontextmanager
    async def operation(self, context_id: str):
        """Serialize one live operation and make it drainable by release."""
        ctx = self.ctx_manager.require_context(context_id)
        try:
            async with ctx.operation_lock:
                # Registration follows lock acquisition so a queued waiter
                # cannot replace the task which is actually touching pages.
                registered = await self.ctx_manager.operation_started(context_id)
                if registered is not ctx:
                    raise InvalidCommand("context identity changed before operation")
                yield ctx
                await self.ctx_manager.operation_still_owned(context_id, ctx)
        finally:
            await self.ctx_manager.operation_finished(context_id)

    async def allocate(
        self,
        context_id: str,
        websites: list[Website],
        hooks: list[Hook],
        cleanup_capability: str | None = None,
        *,
        incoming_remaining_seconds: float | None = None,
    ):
        budget_started_at = time.monotonic()
        # Direct Instance callers are a compatibility/test-only boundary;
        # Master normally supplies the durable descriptor before dispatch.
        cleanup_capability = cleanup_capability or secrets.token_urlsafe(32)
        web_descriptors = _validated_web_bindings(context_id, websites)
        await self.ctx_manager.create(context_id, websites)
        # ``create`` reserves the browser objects, but the public context is
        # deliberately still CREATING until navigation and after-hooks finish.
        ctx = self.ctx_manager.require_context(context_id, allow_creating=True)
        # Install every declared server-reset cookie before *any* navigation;
        # concurrent page loads must not let one origin create state first.
        for web_binding in web_descriptors.values():
            await ctx.context.add_cookies([{
                "name": web_binding.cookie_name,
                "value": web_binding.cookie_value,
                "url": web_binding.origin,
            }])
            self._web_bindings.setdefault(context_id, {})[web_binding.website_id] = web_binding
            self.ctx_manager._entries[context_id].web_bindings[web_binding.website_id] = web_binding

        async def load_website(website: Website) -> None:
            page, _ = self.ctx_manager.require_page(
                ctx.context_id, website.website_id, allow_creating=True
            )
            url = _native_entry_url(website)
            web_binding = web_descriptors.get(website.website_id)
            if website.surface == "native":
                parsed = urlsplit(url)
                # Install the cleanup-only descriptor before navigation: an
                # admission may exist even if the response never delivered its
                # SID/app cookies.
                self._native_bindings[context_id] = NativeBinding(
                    context_id=context_id,
                    website_id=website.website_id,
                    origin=urlunsplit((parsed.scheme, parsed.netloc, "", "", "")),
                    session_id=None,
                    app=None,
                    cleanup_capability=cleanup_capability,
                )
                self.ctx_manager._entries[context_id].native_bindings[website.website_id] = (
                    self._native_bindings[context_id]
                )
                # Register the secret only on the gateway's lifecycle endpoint.
                # The browser receives a non-secret context correlation cookie.
                bind_timeout = None
                if incoming_remaining_seconds is not None:
                    bind_timeout = incoming_remaining_seconds - (time.monotonic() - budget_started_at)
                    if bind_timeout <= 0:
                        raise InstanceError("allocation remaining budget expired before native binding", 504, retryable=True)
                async with httpx.AsyncClient(timeout=bind_timeout) as client:
                    response = await client.post(
                        f"{urlunsplit((parsed.scheme, parsed.netloc, '', '', ''))}/bind-context",
                        json={"context_id": context_id, "website_id": website.website_id,
                              "cleanup_capability": cleanup_capability},
                    )
                if response.status_code != 200:
                    raise InstanceError("native context binding failed", 503, retryable=True)
                await ctx.context.add_cookies([{
                    "name": "__surfgym_context_id", "value": context_id,
                    "url": urlunsplit((parsed.scheme, parsed.netloc, '', '', "")),
                    "httpOnly": True,
                }])
            try:
                goto_kwargs: dict[str, object] = {"wait_until": "domcontentloaded"}
                if incoming_remaining_seconds is not None:
                    remaining_seconds = incoming_remaining_seconds - (
                        time.monotonic() - budget_started_at
                    )
                    if remaining_seconds <= 0:
                        raise InstanceError(
                            "allocation remaining budget expired before navigation", 504, retryable=True
                        )
                    goto_kwargs["timeout"] = remaining_seconds * 1000.0
                response = await page.goto(url, **goto_kwargs)
            except InstanceError:
                raise
            except Exception:
                # Playwright includes the navigated URL in its error text.
                # That URL carries a cleanup capability for native entries, so
                # never preserve the original exception chain for logging.
                raise InstanceError(
                    "Initial navigation failed before a response", 503, retryable=True
                ) from None
            if response is not None and not 200 <= response.status < 300:
                retryable = response.status == 429 or 500 <= response.status < 600
                raise InstanceError(
                    f"Initial navigation failed with HTTP {response.status}: {website.url}",
                    response.status,
                    retryable=retryable,
                )
            ctx.entered_page_ids.add(website.website_id)
            if website.surface == "native":
                cookies = {cookie["name"]: cookie["value"] for cookie in await ctx.context.cookies(url)}
                session_id = cookies.get("surfgym_session_id")
                app = cookies.get("surfgym_app")
                if not session_id or not app:
                    # The capability descriptor remains valid for release of an
                    # admission that completed before its response was lost.
                    return
                parsed = urlsplit(url)
                self._native_bindings[context_id] = NativeBinding(
                    context_id=context_id, website_id=website.website_id,
                    origin=urlunsplit((parsed.scheme, parsed.netloc, "", "", "")),
                    session_id=session_id, app=app,
                    cleanup_capability=cleanup_capability,
                )
                self.ctx_manager._entries[context_id].native_bindings[website.website_id] = (
                    self._native_bindings[context_id]
                )

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

        await self._run_hooks(context_id, hooks, timing="after", allow_creating=True)
        await self.ctx_manager.activate(context_id)

    async def release(self, context_id: str, hooks: list[Hook]):
        # A lost reply must join the original cleanup, never begin a second
        # cleanup which could act on a successor lease.
        task = await self.ctx_manager.get_or_start_release_task(
            context_id, lambda: self._release_once(context_id, hooks)
        )
        if task is None:
            return
        try:
            # The HTTP request is only a waiter.  Its cancellation must not
            # cancel the retained cleanup owner.
            await asyncio.shield(task)
        except BaseException:
            raise

    async def _release_once(self, context_id: str, hooks: list[Hook]) -> None:
        try:
            entry = await self.ctx_manager.seal(context_id)
            create_task = entry.create_task
            if create_task is not None and create_task is not asyncio.current_task():
                create_task.cancel()
                # A navigation request can already have completed with its
                # own failure by the time Master asks us to release it.  That
                # failure explains the public allocation result, but it must
                # not prevent this retained release owner from draining the
                # browser before it dispatches the native reset capability.
                # Awaiting the task is the drain barrier; its terminal result
                # is deliberately not the release result.
                await asyncio.gather(create_task, return_exceptions=True)
            active_task = entry.active_operation_task
            if active_task is not None and active_task is not asyncio.current_task():
                active_task.cancel()
                with suppress(asyncio.CancelledError):
                    await active_task

            ctx = entry.context
            if ctx is not None:
                async with ctx.operation_lock:
                    native_page_ids = set(getattr(ctx, "native_page_ids", ()))
                    web_hooks = [hook for hook in hooks if hook.website_id not in native_page_ids]
                    await self._run_hooks(
                        context_id, web_hooks, timing="before", entered_only=True,
                        allow_closing=True,
                    )
                    await self.ctx_manager._delete_locked(context_id, ctx)

            await self.ctx_manager.close_partial_browser_context(context_id)

            # Physical browser close does not release capacity.  Retained native
            # bindings keep the entry CLOSING until Docker confirms cleanup.
            bindings = tuple(entry.native_bindings.values()) or tuple(
                binding for binding in [self._native_bindings.get(context_id)] if binding is not None
            )
            await self._release_native_bindings_until_terminal(
                tuple(cast(NativeBinding, binding) for binding in bindings)
            )
            self._native_bindings.pop(context_id, None)
            entry.native_bindings.clear()
            for binding in tuple(entry.web_bindings.values()):
                await self._release_web_binding(cast(WebBinding, binding))
            self._web_bindings.pop(context_id, None)
            entry.web_bindings.clear()
            await self.ctx_manager.mark_closed(context_id)
        except InstanceError as exc:
            # An UNKNOWN cleanup outcome remains owned by this terminal task.
            # Retrying callers replay its result instead of dispatching a new
            # capability request against a successor lease.
            if exc.message == "native binding cleanup confirmation is UNKNOWN":
                raise
            # Web finalization retains its existing retry semantics.  It has
            # no capability-bound poll loop and is outside this native cleanup
            # ownership horizon.
            current = asyncio.current_task()
            if current is not None:
                await self.ctx_manager.clear_release_task(context_id, current)
            raise
        except BaseException:
            current = asyncio.current_task()
            if current is not None:
                await self.ctx_manager.clear_release_task(context_id, current)
            raise

    async def _release_native_bindings_until_terminal(
        self, bindings: tuple[NativeBinding, ...]
    ) -> None:
        deadline = time.monotonic() + self.binding_cleanup_horizon_seconds
        for binding in bindings:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise InstanceError(
                        "native binding cleanup confirmation is UNKNOWN",
                        503,
                        retryable=True,
                    )
                try:
                    await self._release_native_binding(
                        binding,
                        timeout_seconds=min(
                            self.binding_cleanup_request_timeout_seconds,
                            remaining,
                        ),
                    )
                    break
                except InstanceError:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise InstanceError(
                            "native binding cleanup confirmation is UNKNOWN",
                            503,
                            retryable=True,
                        ) from None
                    await asyncio.sleep(
                        min(self.binding_cleanup_retry_interval_seconds, remaining)
                    )

    async def _release_native_binding(
        self,
        binding: NativeBinding,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=(
                    self.binding_cleanup_request_timeout_seconds
                    if timeout_seconds is None
                    else timeout_seconds
                )
            ) as client:
                response = await client.post(
                    f"{binding.origin}/release-context",
                    json={
                        "context_id": binding.context_id,
                        "website_id": binding.website_id,
                        "cleanup_capability": binding.cleanup_capability,
                    },
                    cookies={
                        key: value
                        for key, value in {
                            "surfgym_session_id": binding.session_id,
                            "surfgym_app": binding.app,
                        }.items()
                        if value is not None
                    },
                )
        except httpx.RequestError as exc:
            raise InstanceError("native binding release response is UNKNOWN", 503, retryable=True) from exc
        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            raise InstanceError("native binding release response is malformed", 503, retryable=True) from exc
        if (
            response.status_code != 200
            or not isinstance(body, dict)
            or body.get("ok") is not True
            or body.get("cleanup_complete") is not True
        ):
            raise InstanceError("native binding release is incomplete", 503, retryable=True)

    async def _release_web_binding(self, binding: WebBinding) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{binding.origin}{binding.reset_path}",
                    headers={"X-SurfGym-Finalize": "1"},
                    cookies={binding.cookie_name: binding.cookie_value},
                )
        except httpx.RequestError as exc:
            raise InstanceError("web binding finalization response is UNKNOWN", 503, retryable=True) from exc
        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            raise InstanceError("web binding finalization response is malformed", 503, retryable=True) from exc
        if (
            response.status_code != 200
            or not isinstance(body, dict)
            or body.get("ok") is not True
            or body.get("cleanup_complete") is not True
        ):
            raise InstanceError("web binding finalization is incomplete", 503, retryable=True)

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
            return await self._artifact_locked(context_id, artifact, ctx)

    async def _artifact_locked(
        self, context_id: str, artifact: ArtifactSpec, ctx
    ) -> ArtifactPayload:
        if self.ctx_manager.require_context(context_id) is not ctx:
            raise InvalidCommand("context identity changed before artifact retrieval")
        else:
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
        allow_creating: bool = False,
        allow_closing: bool = False,
    ):
        selected_hooks = (hook for hook in hooks if hook.timing == timing)
        if entered_only:
            entered_page_ids = self._context_for_lifecycle(
                context_id, allow_creating=allow_creating, allow_closing=allow_closing
            ).entered_page_ids
            selected_hooks = (
                hook for hook in selected_hooks if hook.website_id in entered_page_ids
            )

        for website_id, website_hooks in groupby(
            selected_hooks,
            key=lambda hook: hook.website_id,
        ):
            ctx = self._context_for_lifecycle(
                context_id, allow_creating=allow_creating, allow_closing=allow_closing
            )
            page = ctx.pages.get(website_id)
            if page is None:
                raise InvalidCommand("no page")
            page, _ = page
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

    def _context_for_lifecycle(
        self, context_id: str, *, allow_creating: bool, allow_closing: bool
    ):
        return self.ctx_manager.require_context(
            context_id, allow_creating=allow_creating, allow_closing=allow_closing
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


def _native_entry_url(website: Website) -> str:
    if website.surface != "native":
        return website.url
    parsed = urlsplit(website.url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    return urlunsplit(parsed._replace(query=urlencode(query)))


_COOKIE_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def _validated_web_bindings(context_id: str, websites: list[Website]) -> dict[str, WebBinding]:
    bindings: dict[str, WebBinding] = {}
    hostname_scopes: dict[tuple[str, str], str] = {}
    for website in websites:
        descriptor = website.server_reset
        if descriptor is None:
            continue
        parsed = urlsplit(descriptor.origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise InvalidCommand("invalid server_reset origin")
        if not _COOKIE_TOKEN.fullmatch(descriptor.cookie_name):
            raise InvalidCommand("invalid server_reset cookie name")
        if (
            not descriptor.reset_path.startswith("/")
            or descriptor.reset_path.startswith("//")
            or "?" in descriptor.reset_path
            or "#" in descriptor.reset_path
        ):
            raise InvalidCommand("invalid server_reset reset path")
        origin = descriptor.origin.rstrip("/")
        scope = (parsed.hostname.lower(), descriptor.cookie_name)
        existing_origin = hostname_scopes.setdefault(scope, origin)
        if existing_origin != origin:
            raise InvalidCommand("conflicting server_reset cookie scope across origins")
        bindings[website.website_id] = WebBinding(
            context_id=context_id,
            website_id=website.website_id,
            origin=origin,
            cookie_name=descriptor.cookie_name,
            reset_path=descriptor.reset_path,
            cookie_value=web_cleanup_cookie(context_id, origin, descriptor.cookie_name),
        )
    return bindings
