import asyncio
from types import SimpleNamespace

import pytest
from surfgym_contracts.task import Hook
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker


def test_release_retains_context_when_before_hook_fails_then_deletes_on_retry() -> None:
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    deleted_context_ids: list[str] = []
    hook_attempts = 0

    async def run_hooks(*_args, **_kwargs) -> None:
        nonlocal hook_attempts
        hook_attempts += 1
        if hook_attempts == 1:
            raise RuntimeError("fixture bridge is unavailable")

    async def delete(context_id: str) -> None:
        deleted_context_ids.append(context_id)

    context = SimpleNamespace(operation_lock=asyncio.Lock())
    worker._run_hooks = run_hooks  # type: ignore[method-assign]
    worker.ctx_manager = SimpleNamespace(
        delete=delete,
        require_context=lambda _context_id: context,
    )

    with pytest.raises(RuntimeError, match="fixture bridge is unavailable"):
        asyncio.run(
            worker.release(
                "context-id",
                [Hook(timing="before", script="window.surfgym.get({})")],
            )
        )

    # A failed Docker release hook means the fixture may not yet be reset.  The
    # context must remain available so the Master can retry the same release.
    assert deleted_context_ids == []

    asyncio.run(
        worker.release(
            "context-id",
            [Hook(timing="before", script="window.surfgym.get({})")],
        )
    )

    assert hook_attempts == 2
    assert deleted_context_ids == ["context-id"]
