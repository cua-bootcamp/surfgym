import pytest
from pydantic import ValidationError
from surfgym_contracts.task import Task


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
