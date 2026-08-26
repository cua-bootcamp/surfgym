from io import StringIO
from pathlib import Path
from typing import TextIO

from pytest import MonkeyPatch
from surfgym_contracts.task import Website
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


def test_docker_fixture_urls_do_not_receive_the_generic_page_script() -> None:
    manager = ContextManager(contexts_per_instance=1, vw=1280, vh=720)

    assert not manager.should_inject_page_script(Website(url="http://localhost:53001/gimp"))
    assert not manager.should_inject_page_script(
        Website(url="http://desktop.localhost:55301/gimp", surface="native")
    )
    assert manager.should_inject_page_script(Website(url="http://127.0.0.1:3000/word"))


def test_context_manager_configures_each_surface_independently() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.viewport: dict[str, int] | None = None
            self.init_scripts: list[str] = []

        async def set_viewport_size(self, viewport: dict[str, int]) -> None:
            self.viewport = viewport

        async def add_init_script(self, *, script: str) -> None:
            self.init_scripts.append(script)

    class FakeContext:
        def __init__(self) -> None:
            self.pages: list[FakePage] = []

        async def new_page(self) -> FakePage:
            page = FakePage()
            self.pages.append(page)
            return page

        async def close(self) -> None:
            return None

    class FakeBrowser:
        def __init__(self) -> None:
            self.context = FakeContext()

        async def new_context(self, **_options: object) -> FakeContext:
            return self.context

    async def scenario() -> None:
        browser = FakeBrowser()
        manager = ContextManager(contexts_per_instance=1, vw=1280, vh=720)
        manager._b = browser

        await manager.create(
            "ctx",
            [
                Website(website_id="web", url="http://127.0.0.1:3000/word"),
                Website(
                    website_id="native",
                    url="http://desktop.localhost:55301/gimp",
                    surface="native",
                ),
            ],
        )

        web_page, native_page = browser.context.pages
        assert web_page.viewport == {"width": 640, "height": 720}
        assert native_page.viewport == {"width": 640, "height": 720}
        assert web_page.init_scripts == [manager.page_script]
        assert native_page.init_scripts == []

    import asyncio

    asyncio.run(scenario())


def test_context_manager_can_opt_into_https_certificate_errors() -> None:
    class FakeContext:
        async def new_page(self):
            class FakePage:
                async def set_viewport_size(self, _viewport: dict[str, int]) -> None:
                    return None

                async def add_init_script(self, *, script: str) -> None:
                    return None

            return FakePage()

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
