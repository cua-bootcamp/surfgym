from __future__ import annotations

import pytest
from surfgym_contracts.task import ServerReset, Website
from surfgym_runtime.wavepool.instance.error import InstanceError
from surfgym_runtime.wavepool.instance.service import WebBinding, PlaywrightBrowserWorker, _validated_web_bindings
from surfgym_runtime.wavepool.instance import service as instance_service
from surfgym_runtime.wavepool.instance.session import ContextManager


def test_server_reset_binding_uses_shared_cookie_vector() -> None:
    bindings = _validated_web_bindings("5e9408dc-75b7-4a54-9b94-e9ebb2749f1e", [
        Website(website_id="web", url="http://127.0.0.1:3002/", server_reset=ServerReset(
            origin="http://127.0.0.1:3002", cookie_name="surfgym_session_id", reset_path="/api/state"
        ))
    ])
    assert bindings["web"].cookie_value == "df46aa25-7fb3-5207-addd-ee140829bdf5"


def test_server_reset_rejects_shared_host_cookie_across_ports() -> None:
    websites = [
        Website(website_id="one", url="http://127.0.0.1:3000/", server_reset=ServerReset(origin="http://127.0.0.1:3000", cookie_name="sid", reset_path="/reset")),
        Website(website_id="two", url="http://127.0.0.1:3002/", server_reset=ServerReset(origin="http://127.0.0.1:3002", cookie_name="sid", reset_path="/reset")),
    ]
    with pytest.raises(InstanceError, match="conflicting"):
        _validated_web_bindings("ctx", websites)


@pytest.mark.parametrize("status, body, passes", [
    (200, {"ok": True, "cleanup_complete": True}, True),
    (202, {"ok": True, "cleanup_complete": True}, False),
    (404, {"ok": True, "cleanup_complete": True}, False),
    (200, {"ok": True}, False),
])
def test_web_finalizer_requires_terminal_completion_envelope(monkeypatch, status, body, passes) -> None:
    calls = []
    class Response:
        status_code = status; content = b"x"
        def json(self): return body
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def delete(self, url, **kwargs): calls.append((url, kwargs)); return Response()
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", Client)
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    binding = WebBinding("ctx", "web", "http://fixture.test", "sid", "/api/state", "cookie")
    if passes:
        import asyncio; asyncio.run(worker._release_web_binding(binding))
        assert calls == [("http://fixture.test/api/state", {"headers": {"X-SurfGym-Finalize": "1"}, "cookies": {"sid": "cookie"}})]
    else:
        import asyncio
        with pytest.raises(InstanceError): asyncio.run(worker._release_web_binding(binding))


def test_native_incomplete_http_success_is_normalized_to_retryable_503(monkeypatch) -> None:
    class Response:
        status_code = 200; content = b"{}"
        def json(self): return {}
    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == instance_service.DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS

        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def post(self, *_args, **_kwargs): return Response()
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", Client)
    import asyncio
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    with pytest.raises(InstanceError) as error:
        asyncio.run(worker._release_native_binding(instance_service.NativeBinding("ctx", "native", "http://fixture.test", None, None, "cap")))
    assert error.value.status_code == 503 and error.value.retryable is True


def test_all_server_reset_cookies_are_installed_before_any_navigation() -> None:
    import asyncio
    events = []
    class Page:
        async def set_viewport_size(self, _): pass
        async def add_init_script(self, **_): pass
        async def goto(self, url, **_): events.append(("goto", url)); return None
        async def close(self): pass
    class BrowserContext:
        async def add_cookies(self, cookies): events.append(("cookie", cookies[0]["url"]))
        async def new_page(self): return Page()
        async def close(self): pass
        async def cookies(self, _): return []
    class Browser:
        async def new_context(self, **_): return BrowserContext()
    async def scenario():
        worker = PlaywrightBrowserWorker(contexts_per_instance=1)
        worker.ctx_manager._b = Browser()  # type: ignore[assignment]
        sites = [
            Website(website_id="one", url="http://one.test/", server_reset=ServerReset(origin="http://one.test", cookie_name="sid", reset_path="/reset")),
            Website(website_id="two", url="http://two.test/", server_reset=ServerReset(origin="http://two.test", cookie_name="sid", reset_path="/reset")),
        ]
        await worker.allocate("ctx", sites, [])
        assert [kind for kind, _ in events[:2]] == ["cookie", "cookie"]
        assert all(kind == "cookie" for kind, _ in events[:events.index(next(item for item in events if item[0] == "goto"))])
    asyncio.run(scenario())
