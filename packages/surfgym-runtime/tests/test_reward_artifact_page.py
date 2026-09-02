from __future__ import annotations

import asyncio
import base64
import hashlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from surfgym_contracts.protocol.artifact import ArtifactPayload, ArtifactSpec
from surfgym_runtime.gateway import transport as gateway_transport
from surfgym_runtime.wavepool.instance.error import InstanceError, InvalidCommand
from surfgym_runtime.wavepool.instance.server import create_app
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker


def _payload(path: str = "Desktop/out.txt", raw: bytes = b"artifact") -> dict[str, object]:
    return {
        "ok": True,
        "path": path,
        "mime_type": "text/plain",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "encoding": "base64",
        "data": base64.b64encode(raw).decode("ascii"),
    }


def test_instance_client_serializes_exact_nested_artifact_request(
    monkeypatch: MonkeyPatch,
) -> None:
    raw = b"artifact"
    expected = ArtifactPayload.model_validate(
        {k: v for k, v in _payload(raw=raw).items() if k != "ok"}
    )
    observed: dict[str, object] = {}

    def record_request(
        url: str,
        response_schema: object,
        *,
        operation: str,
        timeout: float,
        **kwargs: object,
    ) -> ArtifactPayload:
        observed.update(
            url=url,
            response_schema=response_schema,
            operation=operation,
            timeout=timeout,
            **kwargs,
        )
        return expected

    monkeypatch.setattr(gateway_transport, "_request_model", record_request)
    client = gateway_transport.InstanceClient(host="instance.test", port=19000)

    result = client.artifact(
        context_id="context-id",
        artifact=ArtifactSpec(path="Desktop/out.txt", max_bytes=128),
        timeout=2.5,
    )

    assert result == expected
    assert observed == {
        "url": "http://instance.test:19000/artifact",
        "response_schema": ArtifactPayload,
        "operation": "instance.artifact",
        "timeout": 2.5,
        "params": {"context_id": "context-id"},
        "json": {"artifact": {"path": "Desktop/out.txt", "max_bytes": 128}},
    }


def test_instance_artifact_route_requires_exact_nested_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    observed: list[tuple[str, ArtifactSpec]] = []

    async def no_op(_self: PlaywrightBrowserWorker) -> None:
        return None

    async def artifact(
        _self: PlaywrightBrowserWorker,
        context_id: str,
        spec: ArtifactSpec,
    ) -> ArtifactPayload:
        observed.append((context_id, spec))
        return ArtifactPayload.model_validate(
            {k: v for k, v in _payload(spec.path).items() if k != "ok"}
        )

    monkeypatch.setattr(PlaywrightBrowserWorker, "open", no_op)
    monkeypatch.setattr(PlaywrightBrowserWorker, "close", no_op)
    monkeypatch.setattr(PlaywrightBrowserWorker, "artifact", artifact, raising=False)

    with TestClient(create_app(contexts_per_instance=1)) as client:
        response = client.post(
            "/artifact",
            params={"context_id": "context-id"},
            json={"artifact": {"path": "Desktop/out.txt", "max_bytes": 128}},
        )
        assert response.status_code == 200
        assert response.json()["path"] == "Desktop/out.txt"

        for invalid in (
            {"path": "Desktop/out.txt", "max_bytes": 128},
            {"artifact": {"path": "Desktop/out.txt", "max_bytes": 128}, "extra": 1},
            {"artifact": {"path": "Desktop/out.txt", "max_bytes": 128, "extra": 1}},
        ):
            assert (
                client.post(
                    "/artifact", params={"context_id": "context-id"}, json=invalid
                ).status_code
                == 422
            )

    assert observed == [("context-id", ArtifactSpec(path="Desktop/out.txt", max_bytes=128))]


class _Page:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[str, object]] = []
        self.started = asyncio.Event()
        self.allow = asyncio.Event()
        self.allow.set()

    async def evaluate(self, script: str, argument: object) -> object:
        self.calls.append((script, argument))
        self.started.set()
        await self.allow.wait()
        return self.result


class _ContextManager:
    def __init__(self, page: _Page, native_page_ids: tuple[str, ...]) -> None:
        self.page = page
        self.active = True
        self.deleted = asyncio.Event()
        self.allow_delete = asyncio.Event()
        self.allow_delete.set()
        self.context = SimpleNamespace(
            context_id="context-id",
            native_page_ids=native_page_ids,
            entered_page_ids=set(native_page_ids),
            operation_lock=asyncio.Lock(),
        )

    def require_context(self, context_id: str) -> object:
        if context_id != "context-id" or not self.active:
            raise InstanceError("context is no longer active", 409, False)
        return self.context

    def require_page(self, context_id: str, website_id: str) -> tuple[_Page, None]:
        assert self.require_context(context_id) is self.context
        assert website_id in self.context.native_page_ids
        return self.page, None

    async def delete(self, context_id: str) -> None:
        assert self.require_context(context_id) is self.context
        self.deleted.set()
        await self.allow_delete.wait()
        self.active = False


def _worker(manager: _ContextManager) -> PlaywrightBrowserWorker:
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = manager  # type: ignore[assignment]
    return worker


def test_artifact_projects_exact_success_envelope_and_checks_request_bounds() -> None:
    page = _Page(_payload())
    manager = _ContextManager(page, ("native",))

    payload = asyncio.run(
        _worker(manager).artifact("context-id", ArtifactSpec(path="Desktop/out.txt", max_bytes=128))
    )

    assert payload.path == "Desktop/out.txt"
    assert page.calls[0][1] == {"path": "Desktop/out.txt", "max_bytes": 128}
    script = page.calls[0][0]
    assert 'fetch("/artifact"' in script
    assert 'credentials: "same-origin"' in script


@pytest.mark.parametrize(
    "result",
    [
        {k: v for k, v in _payload().items() if k != "ok"},
        {**_payload(), "ok": False},
        {**_payload(), "extra": 1},
        {k: v for k, v in _payload().items() if k != "data"},
        {**_payload(), "path": "Desktop/other.txt"},
        {**_payload(raw=b"x" * 129), "size": 129},
        {**_payload(), "data": "YXJ0aWZhY3Q=\n"},
        {**_payload(), "mime_type": "Text/Plain"},
        {**_payload(), "sha256": "0" * 64},
    ],
)
def test_artifact_rejects_non_exact_or_invalid_success_envelope(result: object) -> None:
    worker = _worker(_ContextManager(_Page(result), ("native",)))

    with pytest.raises(InvalidCommand):
        asyncio.run(
            worker.artifact("context-id", ArtifactSpec(path="Desktop/out.txt", max_bytes=128))
        )


@pytest.mark.parametrize("native_page_ids", [(), ("one", "two")])
def test_artifact_requires_exactly_one_native_surface(
    native_page_ids: tuple[str, ...],
) -> None:
    page = _Page(_payload())
    worker = _worker(_ContextManager(page, native_page_ids))

    with pytest.raises(InvalidCommand, match="exactly one native surface"):
        asyncio.run(
            worker.artifact("context-id", ArtifactSpec(path="Desktop/out.txt", max_bytes=128))
        )
    assert page.calls == []


def test_artifact_first_serializes_release_on_the_same_context() -> None:
    async def scenario() -> tuple[ArtifactPayload, bool]:
        page = _Page(_payload())
        page.allow.clear()
        manager = _ContextManager(page, ("native",))
        worker = _worker(manager)

        artifact_task = asyncio.create_task(
            worker.artifact("context-id", ArtifactSpec(path="Desktop/out.txt", max_bytes=128))
        )
        await page.started.wait()
        release_task = asyncio.create_task(worker.release("context-id", []))
        await asyncio.sleep(0)
        release_waited = not manager.deleted.is_set()
        page.allow.set()
        payload = await artifact_task
        await release_task
        return payload, release_waited

    payload, release_waited = asyncio.run(scenario())
    assert payload.path == "Desktop/out.txt"
    assert release_waited is True


def test_release_first_makes_waiting_artifact_fail_closed() -> None:
    async def scenario() -> None:
        manager = _ContextManager(_Page(_payload()), ("native",))
        manager.allow_delete.clear()
        worker = _worker(manager)

        release_task = asyncio.create_task(worker.release("context-id", []))
        await manager.deleted.wait()
        artifact_task = asyncio.create_task(
            worker.artifact("context-id", ArtifactSpec(path="Desktop/out.txt", max_bytes=128))
        )
        await asyncio.sleep(0)
        assert not artifact_task.done()
        manager.allow_delete.set()
        await release_task
        with pytest.raises(InstanceError):
            await artifact_task

    asyncio.run(scenario())
