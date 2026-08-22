from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PACKAGE_ROOT / "src" / "surfgym_task" / "data"


def _json_scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _render_states(states: object, indent: int) -> list[str]:
    if not isinstance(states, list):
        raise ValueError("The 'states' field must be an array.")

    padding = " " * indent
    child_padding = " " * (indent + 2)
    if not states:
        return [f"{padding}[]"]

    lines = [f"{padding}["]
    for index, state in enumerate(states):
        if not isinstance(state, list):
            raise ValueError("Each element of 'states' must be a state array.")
        suffix = "," if index < len(states) - 1 else ""
        compact = json.dumps(
            state,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        lines.append(f"{child_padding}{compact}{suffix}")
    lines.append(f"{padding}]")
    return lines


def _render(value: object, indent: int = 0) -> list[str]:
    padding = " " * indent

    if isinstance(value, dict):
        if not value:
            return [f"{padding}{{}}"]

        items = list(value.items())
        lines = [f"{padding}{{"]
        for index, (key, child) in enumerate(items):
            key_text = json.dumps(key, ensure_ascii=False)
            child_lines = (
                _render_states(child, indent + 2)
                if key == "states"
                else _render(child, indent + 2)
            )
            first = child_lines[0].lstrip(" ")
            lines.append(f"{' ' * (indent + 2)}{key_text}: {first}")
            lines.extend(child_lines[1:])
            if index < len(items) - 1:
                lines[-1] += ","
        lines.append(f"{padding}}}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{padding}[]"]

        lines = [f"{padding}["]
        for index, child in enumerate(value):
            child_lines = _render(child, indent + 2)
            if index < len(value) - 1:
                child_lines[-1] += ","
            lines.extend(child_lines)
        lines.append(f"{padding}]")
        return lines

    return [f"{padding}{_json_scalar(value)}"]


def format_seed_payload(payload: object) -> str:
    if not isinstance(payload, dict):
        raise ValueError("A seed JSON document must be an object.")
    return "\n".join(_render(payload)) + "\n"


def format_seed_file(path: Path, *, check: bool) -> bool:
    original = path.read_text(encoding="utf-8")
    payload = json.loads(original)
    formatted = format_seed_payload(payload)

    if original == formatted:
        return False
    if not check:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(formatted)
    return True


def _seed_paths(inputs: Sequence[Path]) -> list[Path]:
    if not inputs:
        return sorted(DEFAULT_DATA_DIR.glob("*/seeds/*.json"))

    paths: set[Path] = set()
    for input_path in inputs:
        path = input_path.resolve()
        if path.is_file():
            if path.suffix != ".json" or path.parent.name != "seeds":
                raise ValueError(f"Not a seed JSON file: {input_path}")
            paths.add(path)
        elif path.is_dir() and path.name == "seeds":
            paths.update(path.glob("*.json"))
        elif path.is_dir():
            paths.update(path.glob("*/seeds/*.json"))
        else:
            raise FileNotFoundError(input_path)
    return sorted(paths)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format SurfGym seed JSON without expanding a state across lines."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Seed JSON files, seeds directories, or a data directory.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report files that need formatting without modifying them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    changed = [
        path
        for path in _seed_paths(args.paths)
        if format_seed_file(path, check=args.check)
    ]

    action = "would reformat" if args.check else "reformatted"
    for path in changed:
        print(f"{action}: {path}")
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
