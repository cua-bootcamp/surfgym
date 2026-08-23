import asyncio
from typing import Any, cast

import pytest
from surfgym_contracts.task import Hook, Website
from surfgym_runtime.wavepool.instance.error import InstanceError
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import Context, PageLayout


class _NavigationResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _Page:
    def __init__(self, response: _NavigationResponse | None, *, delay: float = 0.0) -> None:
        self.response = response
        self.delay = delay
        self.evaluated_scripts: list[list[str]] = []

    async def goto(self, _url: str, *, wait_until: str):
        assert wait_until == "domcontentloaded"
        await asyncio.sleep(self.delay)
        return self.response

    async def evaluate(self, _expression: str, scripts: list[str]) -> None:
        self.evaluated_scripts.append(scripts)


class _ContextManager:
    def __init__(self, pages: dict[str, _Page]) -> None:
        layout = PageLayout(x=0, y=0, width=100, height=100)
        self.context = Context(
            context_id="context-id",
            context=cast(Any, object()),
            pages={website_id: (cast(Any, page), layout) for website_id, page in pages.items()},
            active_page_id=next(iter(pages)),
        )
        self.deleted_context_ids: list[str] = []

    async def create(self, _context_id: str, _websites: list[Website]) -> None:
        return None

    def require_context(self, _context_id: str):
        return self.context

    def require_page(self, _context_id: str, _website_id: str):
        return self.context.pages[_website_id]

    async def delete(self, context_id: str) -> None:
        self.deleted_context_ids.append(context_id)


def _worker_with_navigation_response(
    response: _NavigationResponse | None,
) -> PlaywrightBrowserWorker:
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = _ContextManager({"_": _Page(response)})  # type: ignore[assignment]
    return worker


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_allocate_rejects_retryable_navigation_status(status_code: int) -> None:
    worker = _worker_with_navigation_response(_NavigationResponse(status_code))

    with pytest.raises(InstanceError) as exc_info:
        asyncio.run(
            worker.allocate(
                "context-id",
                [Website(url="http://fixture.test")],
                [],
            )
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.retryable is True


@pytest.mark.parametrize("status_code", [302, 400, 404])
def test_allocate_rejects_non_retryable_navigation_status(status_code: int) -> None:
    worker = _worker_with_navigation_response(_NavigationResponse(status_code))

    with pytest.raises(InstanceError) as exc_info:
        asyncio.run(
            worker.allocate(
                "context-id",
                [Website(url="http://fixture.test")],
                [],
            )
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.retryable is False


@pytest.mark.parametrize("response", [_NavigationResponse(200), _NavigationResponse(204), None])
def test_allocate_accepts_successful_or_response_less_navigation(
    response: _NavigationResponse | None,
) -> None:
    worker = _worker_with_navigation_response(response)

    asyncio.run(
        worker.allocate(
            "context-id",
            [Website(url="http://fixture.test")],
            [],
        )
    )


def test_failed_allocate_releases_only_successfully_entered_pages() -> None:
    entered_page = _Page(_NavigationResponse(200))
    failed_page = _Page(_NavigationResponse(404))
    manager = _ContextManager({"entered": entered_page, "failed": failed_page})
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = manager  # type: ignore[assignment]
    release_hooks = [
        Hook(website_id="entered", timing="before", script="releaseEntered()"),
        Hook(website_id="failed", timing="before", script="releaseFailed()"),
    ]

    with pytest.raises(InstanceError):
        asyncio.run(
            worker.allocate(
                "context-id",
                [
                    Website(website_id="entered", url="http://entered.test"),
                    Website(website_id="failed", url="http://failed.test"),
                ],
                [],
            )
        )

    asyncio.run(worker.release("context-id", release_hooks))

    assert entered_page.evaluated_scripts == [["releaseEntered()"]]
    assert failed_page.evaluated_scripts == []
    assert manager.deleted_context_ids == ["context-id"]


def test_failed_allocate_waits_for_other_initial_navigations_before_rollback() -> None:
    failed_page = _Page(_NavigationResponse(404))
    late_entered_page = _Page(_NavigationResponse(200), delay=0.2)
    manager = _ContextManager({"failed": failed_page, "entered": late_entered_page})
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = manager  # type: ignore[assignment]

    with pytest.raises(InstanceError):
        asyncio.run(
            worker.allocate(
                "context-id",
                [
                    Website(website_id="failed", url="http://failed.test"),
                    Website(website_id="entered", url="http://entered.test"),
                ],
                [],
            )
        )

    asyncio.run(
        worker.release(
            "context-id",
            [Hook(website_id="entered", timing="before", script="releaseEntered()")],
        )
    )

    assert late_entered_page.evaluated_scripts == [["releaseEntered()"]]


def test_non_retryable_navigation_failure_takes_precedence_after_all_pages_settle() -> None:
    retryable_page = _Page(_NavigationResponse(503))
    non_retryable_page = _Page(_NavigationResponse(404), delay=0.05)
    late_entered_page = _Page(_NavigationResponse(200), delay=0.1)
    manager = _ContextManager(
        {
            "retryable": retryable_page,
            "permanent": non_retryable_page,
            "entered": late_entered_page,
        }
    )
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = manager  # type: ignore[assignment]

    with pytest.raises(InstanceError) as exc_info:
        asyncio.run(
            worker.allocate(
                "context-id",
                [
                    Website(website_id="retryable", url="http://retryable.test"),
                    Website(website_id="permanent", url="http://permanent.test"),
                    Website(website_id="entered", url="http://entered.test"),
                ],
                [],
            )
        )

    asyncio.run(
        worker.release(
            "context-id",
            [Hook(website_id="entered", timing="before", script="releaseEntered()")],
        )
    )

    assert late_entered_page.evaluated_scripts == [["releaseEntered()"]]
    assert exc_info.value.status_code == 404
    assert exc_info.value.retryable is False
