import pytest
from pydantic import ValidationError
from surfgym_contracts.task import Task, Website


def test_task_parses_infeasible_evaluation():
    """Removing the infeasible evaluation variant must reject this task."""
    task = Task.model_validate(
        {
            "task_id": "infeasible-task",
            "instruction": "Report that this task cannot be completed.",
            "website": "http://example.test",
            "evaluation": {"mode": "infeasible"},
        }
    )

    assert task.evaluation.mode == "infeasible"


def test_infeasible_evaluation_round_trips_through_task_json():
    """Dropping the evaluation mode during persistence must break this round trip."""
    task = Task.model_validate(
        {
            "task_id": "infeasible-task",
            "instruction": "Report that this task cannot be completed.",
            "website": "http://example.test",
            "evaluation": {"mode": "infeasible"},
        }
    )

    restored = Task.model_validate_json(task.model_dump_json())

    assert restored == task
    assert restored.evaluation.mode == "infeasible"


def test_infeasible_evaluation_rejects_capability_field():
    """Adding fixture metadata to evaluation must remain invalid schema input."""
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "task_id": "infeasible-task",
                "instruction": "Report that this task cannot be completed.",
                "website": "http://example.test",
                "evaluation": {
                    "mode": "infeasible",
                    "capability": "spreadsheet.sparkline",
                },
            }
        )


@pytest.mark.parametrize(
    "evaluation",
    [
        {"mode": "criteria", "criteria": {"value": "done", "selector": "#result"}},
        {"mode": "llm"},
    ],
)
def test_existing_evaluation_modes_still_parse(evaluation: dict[str, object]):
    task = Task.model_validate(
        {
            "task_id": "existing-task",
            "instruction": "Complete the existing task.",
            "website": "http://example.test",
            "evaluation": evaluation,
        }
    )

    assert task.evaluation.mode in {"criteria", "llm"}


def test_hybrid_task_keeps_per_website_criteria_and_release_hooks():
    task = Task.model_validate(
        {
            "task_id": "hybrid-task",
            "instruction": "Copy the web value into the native application.",
            "website": [
                {"website_id": "web", "url": "http://web.localhost:3200"},
                {"website_id": "native", "url": "http://desktop.localhost:53001/gimp"},
            ],
            "evaluation": {
                "mode": "criteria",
                "criteria": {
                    "website_id": "native",
                    "mode": "console",
                    "script": "() => window.surfgym.get({})",
                    "value": {"saved": True},
                },
            },
            "lifecycle_hooks": {
                "release": [
                    {
                        "website_id": "web",
                        "timing": "before",
                        "script": "window.surfgym.get({})",
                    },
                    {
                        "website_id": "native",
                        "timing": "before",
                        "script": "window.surfgym.get({})",
                    },
                ]
            },
        }
    )

    assert [website.website_id for website in task.website] == ["web", "native"]
    assert [website.surface for website in task.website] == ["web", "native"]
    assert task.evaluation.criteria[0].website_id == "native"
    assert [hook.website_id for hook in task.lifecycle_hooks.release] == ["web", "native"]


@pytest.mark.parametrize(
    ("website", "match"),
    [
        (
            [
                {"website_id": "web", "url": "http://web.localhost:3200"},
                {"website_id": "web", "url": "http://desktop.localhost:53001/gimp"},
            ],
            "website_id values must be unique",
        ),
        (
            [{"website_id": "web", "url": "http://web.localhost:3200"}],
            "website_id references must name a website",
        ),
    ],
)
def test_task_rejects_ambiguous_or_unknown_website_ids(website: list[dict[str, str]], match: str):
    with pytest.raises(ValidationError, match=match):
        Task.model_validate(
            {
                "task_id": "invalid-website-ids",
                "instruction": "Invalid website references must fail early.",
                "website": website,
                "evaluation": {"mode": "criteria", "criteria": {"value": "done"}},
            }
        )


def test_task_rejects_more_than_one_native_surface() -> None:
    with pytest.raises(ValidationError, match="at most one native surface"):
        Task.model_validate(
            {
                "task_id": "two-native-surfaces",
                "instruction": "Unsupported native-to-native task.",
                "website": [
                    {
                        "website_id": "first",
                        "url": "http://desktop.localhost:55301/gimp",
                        "surface": "native",
                    },
                    {
                        "website_id": "second",
                        "url": "http://desktop.localhost:55302/impress",
                        "surface": "native",
                    },
                ],
                "evaluation": {"mode": "criteria", "criteria": {"value": "done"}},
            }
        )


def test_website_surface_is_explicit_on_alternate_port_and_legacy_53001_is_inferred() -> None:
    explicit = Website(
        url="http://desktop.localhost:55301/gimp",
        surface="native",
    )
    legacy = Website(url="http://localhost:53001/gimp")
    ordinary_web = Website(url="http://localhost:55301/gimp")

    assert explicit.surface == "native"
    assert legacy.surface == "native"
    assert ordinary_web.surface == "web"


def test_hybrid_task_rejects_shared_hostname_cookie_scope() -> None:
    with pytest.raises(ValidationError, match="different hostnames for cookie isolation"):
        Task.model_validate(
            {
                "task_id": "shared-cookie-host",
                "instruction": "This would silently replace the Docker session cookie.",
                "website": [
                    {
                        "website_id": "web",
                        "url": "http://localhost:3200",
                    },
                    {
                        "website_id": "native",
                        "url": "http://localhost:55301/gimp",
                        "surface": "native",
                    },
                ],
                "evaluation": {"mode": "criteria", "criteria": {"value": "done"}},
            }
        )
