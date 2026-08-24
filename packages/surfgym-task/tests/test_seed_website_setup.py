import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import TypeAdapter, ValidationError
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

    assert setup == {
        "files": [{"source": "video.webm", "target": "desktop"}]
    }


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
