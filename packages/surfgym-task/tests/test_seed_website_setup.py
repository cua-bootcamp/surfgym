import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import TypeAdapter, ValidationError
from surfgym_task.io import SeedReader
from surfgym_task.seed import RawSeedTask, RawSeedWebsite

DATA_ROOT = Path(__file__).parents[1] / "src" / "surfgym_task" / "data"


def test_setup_is_serialized_as_one_structured_query_value() -> None:
    website = RawSeedWebsite.model_validate(
        {
            "base": "http://localhost:53001/impress",
            "setup_files": [
                {"source": "1.pptx", "target": "desktop"},
                {"source": "media/pic1.png", "target": "desktop"},
            ],
            "open_file": "1.pptx",
            "setup_operations": [
                {
                    "query": [["slide", 2]],
                    "path": ["media", "image"],
                    "value": "pic1.png",
                }
            ],
        }
    )

    query = parse_qs(urlsplit(website.to_url()).query)
    setup = json.loads(query["setup"][0])

    assert setup == {
        "files": [
            {"source": "1.pptx", "target": "desktop"},
            {"source": "media/pic1.png", "target": "desktop"},
        ],
        "open_file": "1.pptx",
        "operations": [
            {
                "query": [["slide", 2]],
                "path": ["media", "image"],
                "value": "pic1.png",
            }
        ],
    }


def test_stage_only_setup_omits_open_file() -> None:
    website = RawSeedWebsite.model_validate(
        {
            "base": "http://localhost:53001/vlc",
            "setup_files": [{"source": "video.webm", "target": "desktop"}],
        }
    )

    setup = json.loads(parse_qs(urlsplit(website.to_url()).query)["setup"][0])

    assert setup == {"files": [{"source": "video.webm", "target": "desktop"}]}


def test_operation_only_setup_is_serialized_for_chrome() -> None:
    website = RawSeedWebsite.model_validate(
        {
            "base": "http://localhost:53001/chrome",
            "setup_operations": [
                {
                    "kind": "chrome_open_tabs",
                    "urls": ["https://example.test/"],
                }
            ],
        }
    )

    setup = json.loads(parse_qs(urlsplit(website.to_url()).query)["setup"][0])

    assert setup == {
        "operations": [
            {
                "kind": "chrome_open_tabs",
                "urls": ["https://example.test/"],
            }
        ]
    }


def test_generic_setup_serializes_source_apps_and_launches_exactly() -> None:
    website = RawSeedWebsite.model_validate(
        {
            "base": "http://localhost:53001/workspace",
            "setup_files": [
                {
                    "source": "project",
                    "target": "desktop",
                    "source_app": "workspace",
                },
                {
                    "source": "1.pptx",
                    "target": "desktop",
                    "source_app": "impress",
                },
            ],
            "setup_operations": [{"kind": "record_launches"}],
            "launches": [
                {"app": "terminal"},
                {
                    "app": "vscode",
                    "source": "project",
                    "args": ["--reuse-window"],
                },
            ],
        }
    )

    setup = json.loads(parse_qs(urlsplit(website.to_url()).query)["setup"][0])

    assert setup == {
        "files": [
            {
                "source": "project",
                "target": "desktop",
                "source_app": "workspace",
            },
            {
                "source": "1.pptx",
                "target": "desktop",
                "source_app": "impress",
            },
        ],
        "operations": [{"kind": "record_launches"}],
        "launches": [
            {"app": "terminal"},
            {
                "app": "vscode",
                "source": "project",
                "args": ["--reuse-window"],
            },
        ],
    }


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {
                "base": "http://localhost:53001/gimp",
                "setup_files": [{"source": "image.png", "target": "desktop"}],
                "open_file": "other.png",
            },
            "open_file",
        ),
        (
            {
                "base": "http://localhost:53001/impress",
                "setup_files": [{"source": "1.pptx", "target": "desktop"}],
                "setup_operations": [{"path": ["style"], "value": "red"}],
            },
            "setup_operations",
        ),
        (
            {
                "base": "http://localhost:53001/vscode",
                "setup_files": [{"source": "../escape", "target": "fixtures"}],
            },
            "safe relative",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "setup_files": [
                    {"source": "a/report.png", "target": "desktop"},
                    {"source": "b/report.png", "target": "desktop"},
                ],
            },
            "duplicate setup destination",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "setup_files": [{"source": "project", "target": "desktop", "source_app": "GIMP"}],
            },
            "safe app name",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "launches": [],
            },
            "nonempty",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "launches": [{"app": "bad/app"}],
            },
            "safe app name",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "launches": [{"app": "gimp"}, {"app": "gimp"}],
            },
            "duplicate setup launch app",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "setup_files": [{"source": "project", "target": "desktop"}],
                "launches": [{"app": "vscode", "source": "other"}],
            },
            "declared source",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "launches": [{"app": "vscode", "args": ["x"] * 17}],
            },
            "at most 16",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "launches": [{"app": "vscode", "args": [""]}],
            },
            "safe strings",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "launches": [{"app": "vscode", "args": ["x" * 257]}],
            },
            "safe strings",
        ),
        (
            {
                "base": "http://localhost:53001/workspace",
                "setup_files": [{"source": "project", "target": "desktop"}],
                "open_file": "project",
                "launches": [{"app": "terminal"}],
            },
            "mutually exclusive",
        ),
    ],
)
def test_invalid_setup_contract_is_rejected(payload: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        RawSeedWebsite.model_validate(payload)


@pytest.mark.parametrize("domain", ("chrome", "gimp", "impress", "vlc", "vscode"))
def test_existing_desktop_seed_corpus_uses_structured_setup(domain: str) -> None:
    adapter = TypeAdapter[RawSeedTask](RawSeedTask)

    for path in sorted((DATA_ROOT / domain / "seeds").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        website = payload.get("website")
        if isinstance(website, dict):
            assert "setup_file" not in website.get("param", {}), path
            assert "setup_operations" not in website.get("param", {}), path
        adapter.validate_python(payload)


def test_workspace_canary_seed_bytes_and_static_contracts_are_pinned() -> None:
    seed_dir = DATA_ROOT / "workspace" / "seeds"
    expected = {
        "brighten_presentation_image_in_gimp.json": {
            "sha256": "b7f4043d75e308f7eb05d05fb05ac8cf998bcb05ccbc0f2eaa4cce218a1fa59a",
            "source_task_id": "4c26e3f3-3a14-4d86-b44a-d3cedebbb487",
        },
        "open_desktop_project_from_terminal.json": {
            "sha256": "f4c0052ca1aca0bb6f93d1627602add4d2f1712d3b635ce3bfdad72b05b6dfef",
            "source_task_id": "510f64c8-9bcc-4be1-8d30-638705850618",
        },
    }

    paths = sorted(seed_dir.glob("*.json"))

    assert [path.name for path in paths] == sorted(expected)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[path.name]["sha256"]
        assert payload["source_task_id"] == expected[path.name]["source_task_id"]
        assert "artifacts" not in payload

    project = json.loads((seed_dir / "open_desktop_project_from_terminal.json").read_text())
    assert project["website"] == {
        "base": "http://localhost:53001/workspace",
        "setup_files": [{"source": "project", "target": "desktop", "source_app": "workspace"}],
        "launches": [{"app": "terminal"}],
    }
    assert project["states"] == [
        [
            {
                "spec": {
                    "app": "vscode",
                    "format": "process",
                    "command_contains": "/config/Desktop/project",
                },
                "value": True,
            }
        ]
    ]

    image = json.loads((seed_dir / "brighten_presentation_image_in_gimp.json").read_text())
    assert image["website"]["launches"] == [
        {"app": "impress", "source": "1.pptx"},
        {"app": "gimp"},
    ]
    assert image["states"] == [
        [
            {
                "spec": {
                    "app": "gimp",
                    "file": "Desktop/background.png",
                    "format": "image_brightness_similarity",
                    "reference": {"source_app": "impress", "source": "1.pptx", "slide": 1},
                    "min_brightness_delta": 8.0,
                    "min_structure_similarity": 0.8,
                },
                "value": True,
            }
        ]
    ]


def test_workspace_seed_lineage_is_source_only_and_empty_start_is_implicit() -> None:
    seed_dir = DATA_ROOT / "workspace" / "seeds"
    raw_payload = json.loads((seed_dir / "open_desktop_project_from_terminal.json").read_text())
    raw = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(raw_payload)

    assert raw.source_task_id == "510f64c8-9bcc-4be1-8d30-638705850618"

    seeds = {name: seed for seed, name in SeedReader(seed_dir).get_seed()}
    compiled_seed = seeds["open_desktop_project_from_terminal"]
    assert compiled_seed.domain == "workspace"
    assert len(compiled_seed.states) == 2
    assert compiled_seed.states[0].atoms == []
    assert "source_task_id" not in compiled_seed.model_dump(mode="json")


@pytest.mark.parametrize(
    "source_task_id",
    (
        "",
        " leading",
        "trailing ",
        "contains/slash",
        "contains unicode",
        "한글",
        "control\ncharacter",
        "x" * 129,
    ),
)
def test_seed_source_task_id_rejects_unsafe_identifiers(source_task_id: str) -> None:
    payload = json.loads(
        (DATA_ROOT / "workspace" / "seeds" / "open_desktop_project_from_terminal.json").read_text()
    )
    payload["source_task_id"] = source_task_id

    with pytest.raises(ValidationError, match="source_task_id"):
        TypeAdapter[RawSeedTask](RawSeedTask).validate_python(payload)


@pytest.mark.parametrize(
    "source_task_id",
    (
        "a",
        "A0._:-z",
        "x" * 128,
    ),
)
def test_seed_source_task_id_accepts_bounded_ascii_identifiers(source_task_id: str) -> None:
    payload = json.loads(
        (DATA_ROOT / "workspace" / "seeds" / "open_desktop_project_from_terminal.json").read_text()
    )
    payload["source_task_id"] = source_task_id

    raw = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(payload)

    assert raw.source_task_id == source_task_id
