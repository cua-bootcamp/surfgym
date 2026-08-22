from io import StringIO
from pathlib import Path
from typing import TextIO

from pytest import MonkeyPatch
from surfgym_runtime.wavepool.instance.session import ContextManager


def test_context_manager_reads_page_script_as_utf8(monkeypatch: MonkeyPatch):
    script = "window.표식 = true;"

    def open_utf8_only(
        file: str | Path,
        mode: str,
        *,
        encoding: str | None = None,
    ) -> TextIO:
        if encoding != "utf-8":
            raise UnicodeDecodeError("cp949", b"\xed", 0, 1, "invalid sequence")
        return StringIO(script)

    monkeypatch.setattr("builtins.open", open_utf8_only)

    manager = ContextManager(contexts_per_instance=1, vw=1280, vh=720)

    assert manager.page_script == script


def test_context_manager_can_opt_into_https_certificate_errors() -> None:
    class FakeContext:
        async def add_init_script(self, *, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def close(self) -> None:
            return None

    class FakeBrowser:
        def __init__(self) -> None:
            self.options: dict[str, object] | None = None

        async def new_context(self, **options: object) -> FakeContext:
            self.options = options
            return FakeContext()

    async def scenario() -> None:
        browser = FakeBrowser()
        manager = ContextManager(
            contexts_per_instance=1,
            vw=1280,
            vh=720,
            ignore_https_errors=True,
        )
        manager._b = browser

        await manager.create("ctx", [Website(url="https://127.0.0.1:53003/impress")])

        assert browser.options == {
            "viewport": {"width": 1280, "height": 720},
            "ignore_https_errors": True,
        }

    import asyncio

    asyncio.run(scenario())
