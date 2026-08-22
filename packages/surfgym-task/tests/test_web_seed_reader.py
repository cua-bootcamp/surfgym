import json
from pathlib import Path

from pydantic import TypeAdapter
from surfgym_task.io import SeedReader
from surfgym_task.main import _allocate_hooks, _release_hooks, _validate_profile
from surfgym_task.seed import CriteriaSeedTask, Domain, LLMJudgeSeedTask, StateAtom
from surfgym_task.web import DOCKER_FIXTURE_RELEASE_HOOK, WEB_STATE_RESET_HOOK


def _write_seed(seeds_dir: Path, name: str, payload: dict[str, object]) -> None:
    seeds_dir.mkdir(parents=True, exist_ok=True)
    (seeds_dir / f"{name}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _criteria_payload(*, empty_start: bool | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "instruction": "Open the requested attraction detail page.",
        "website": "http://localhost:3200/attractions/searchresults.en-gb.html",
        "states": [
            [
                {
                    "spec": {"target": "url"},
                    "value": "/attractions/detail/attr-002",
                    "match": "contains",
                }
            ]
        ],
    }
    if empty_start is not None:
        payload["empty_start"] = empty_start
    return payload


def test_web_is_a_supported_seed_domain() -> None:
    assert TypeAdapter[Domain](Domain).validate_python("web") == "web"


def test_web_seed_reader_parses_criteria_and_llm(tmp_path: Path) -> None:
    seeds_dir = tmp_path / "web" / "seeds"
    _write_seed(seeds_dir, "criteria", _criteria_payload())
    _write_seed(
        seeds_dir,
        "llm",
        {
            "instruction": "Complete the requested travel search.",
            "website": "http://localhost:3200/flights/search",
            "evaluation": {"mode": "llm"},
        },
    )

    seeds = dict((name, seed) for seed, name in SeedReader(seeds_dir).get_seed())

    assert len(seeds) == 2
    assert sum(isinstance(seed, CriteriaSeedTask) for seed in seeds.values()) == 1
    assert sum(isinstance(seed, LLMJudgeSeedTask) for seed in seeds.values()) == 1
    assert all(seed.domain == "web" for seed in seeds.values())

    criteria = seeds["criteria"]
    assert isinstance(criteria, CriteriaSeedTask)
    assert len(criteria.states) == 2
    assert criteria.states[0].atoms == []
    assert criteria.states[1].atoms[0].value == "/attractions/detail/attr-002"

    llm = seeds["llm"]
    assert isinstance(llm, LLMJudgeSeedTask)


def test_web_criteria_seed_can_override_empty_start(tmp_path: Path) -> None:
    seeds_dir = tmp_path / "web" / "seeds"
    _write_seed(seeds_dir, "criteria", _criteria_payload(empty_start=False))

    [(seed, name)] = list(SeedReader(seeds_dir).get_seed())

    assert name == "criteria"
    assert isinstance(seed, CriteriaSeedTask)
    assert len(seed.states) == 1
    assert seed.states[0].atoms[0].value == "/attractions/detail/attr-002"


def test_web_uses_state_reset_release_hook() -> None:
    assert _release_hooks("web") == [WEB_STATE_RESET_HOOK]
    assert _release_hooks("gimp") == [DOCKER_FIXTURE_RELEASE_HOOK]
    assert _release_hooks("word") == []


def test_web_rejects_snapshot_profile() -> None:
    _validate_profile("web", "ROLLOUT")

    try:
        _validate_profile("web", "SNAPSHOT")
    except ValueError as exc:
        assert str(exc) == "Web seeds support only the ROLLOUT profile."
    else:
        raise AssertionError("Web SNAPSHOT profile should be rejected.")


def test_web_allocate_hooks_apply_state_then_reload_once() -> None:
    atoms = [
        StateAtom(
            spec={"target": "api_state", "path": "data"},
            value={"auth": {"isAuthenticated": True}},
        )
    ]

    hooks = _allocate_hooks("web", atoms)

    assert len(hooks) == 1
    assert "await window.surfgym.set" in hooks[0].script
    assert hooks[0].script.count("location.reload()") == 1
    assert hooks[0].timing == "after"
