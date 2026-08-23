"""Read CUA task bundles out of the released `tasks.tar.zst`.

The archive is a zstd-compressed tar, so there is no random access: pulling one
bundle and pulling a thousand cost the same single streaming pass. Callers pass
the whole id set they want at once.
"""

from __future__ import annotations

import tarfile
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Optional

import zstandard

# macOS AppleDouble sidecars ride along in the archive; they are not bundle files.
_SIDECAR_PREFIX = "._"


@dataclass(frozen=True)
class Bundle:
    task_id: str
    task_json: str
    initial_setup: Optional[str]
    reward: Optional[str]

    @property
    def complete(self) -> bool:
        return self.initial_setup is not None and self.reward is not None


def read_bundles(archive: Path, task_ids: Iterable[str]) -> dict[str, Bundle]:
    wanted = set(task_ids)
    if not wanted:
        return {}

    if archive.suffix.lower() == ".json":
        return _read_extracted_json_bundles(archive, wanted)

    parts: dict[str, dict[str, str]] = {task_id: {} for task_id in wanted}
    remaining = set(wanted)

    for task_id, name, data in _iter_members(archive):
        if task_id not in wanted:
            continue
        parts[task_id][name] = data.decode("utf-8", errors="replace")
        if {"task.json", "initial_setup.py", "reward.py"} <= parts[task_id].keys():
            remaining.discard(task_id)
            if not remaining:
                break

    return {
        task_id: Bundle(
            task_id=task_id,
            task_json=files.get("task.json", ""),
            initial_setup=files.get("initial_setup.py"),
            reward=files.get("reward.py"),
        )
        for task_id, files in parts.items()
        if files
    }


def _read_extracted_json_bundles(
    archive: Path, wanted: set[str]
) -> dict[str, Bundle]:
    """Read the task-id keyed JSON export produced by coverage investigation."""
    loaded = json.loads(archive.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"CUA JSON bundle map must be an object: {archive}")

    bundles: dict[str, Bundle] = {}
    for task_id in wanted:
        files = loaded.get(task_id)
        if not isinstance(files, Mapping):
            continue
        task_json = files.get("task.json", "")
        initial_setup = files.get("initial_setup.py")
        reward = files.get("reward.py")
        if not isinstance(task_json, str):
            raise ValueError(f"CUA JSON bundle {task_id} has a non-string task.json")
        if initial_setup is not None and not isinstance(initial_setup, str):
            raise ValueError(f"CUA JSON bundle {task_id} has a non-string initial_setup.py")
        if reward is not None and not isinstance(reward, str):
            raise ValueError(f"CUA JSON bundle {task_id} has a non-string reward.py")
        bundles[task_id] = Bundle(
            task_id=task_id,
            task_json=task_json,
            initial_setup=initial_setup,
            reward=reward,
        )
    return bundles


def _iter_members(archive: Path) -> Iterator[tuple[str, str, bytes]]:
    decompressor = zstandard.ZstdDecompressor()
    with archive.open("rb") as raw, decompressor.stream_reader(raw) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                head, _, name = member.name.partition("/")
                if not name or name.startswith(_SIDECAR_PREFIX):
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                yield head, name, extracted.read()
