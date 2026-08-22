import asyncio
import sys

from pytest import MonkeyPatch
from surfgym_runtime.wavepool.instance import server, session


class _FakeBrowserType:
    def __init__(self) -> None:
        self.launch_options: dict[str, object] | None = None

    async def launch(self, **kwargs: object) -> object:
        self.launch_options = kwargs
        return object()


class _FakePlaywright:
    def __init__(self, browser_type: _FakeBrowserType) -> None:
        self.chromium = browser_type


class _FakePlaywrightStarter:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self.playwright = playwright

    async def start(self) -> _FakePlaywright:
        return self.playwright


def test_context_manager_launches_a_visible_browser_when_headed_requested(
    monkeypatch: MonkeyPatch,
) -> None:
    browser_type = _FakeBrowserType()
    playwright = _FakePlaywright(browser_type)
    monkeypatch.setattr(
        session,
        "async_playwright",
        lambda: _FakePlaywrightStarter(playwright),
    )

    manager = session.ContextManager(
        contexts_per_instance=1,
        vw=1280,
        vh=720,
        headed=True,
    )

    asyncio.run(manager.open())

    assert browser_type.launch_options == {"headless": False}


def test_instance_cli_accepts_headed_mode(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "instance-server",
            "--host",
            "127.0.0.1",
            "--port",
            "9000",
            "--log-path",
            "D:/logs",
            "--headed",
        ],
    )

    args = server._parse_args()

    assert args.headed is True
