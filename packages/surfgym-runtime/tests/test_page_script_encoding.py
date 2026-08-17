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
