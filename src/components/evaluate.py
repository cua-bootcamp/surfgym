"""
Evaluation logic for converting browser observations into rewards.

- evaluate each rule against collected observations
- combie rule results with and/or semantics
"""

from __future__ import annotations

import re
from typing import Literal, Optional, TypeAlias

from src.components.task import Evaluation, Value

Observation: TypeAlias = Optional[Value]


def evaluate_page_rules(
    evaluation: Evaluation,
    observations: list[Observation],
) -> float:
    checks = tuple(
        _matches(
            observation,
            rule.value,
            match=rule.match,
            normalize_space=rule.normalize_space,
            case_sensitive=rule.case_sensitive,
        )
        for rule, observation in zip(evaluation.rules, observations)
    )

    passed = (
        all(check for check in checks)
        if evaluation.operator == "and"
        else any(check for check in checks)
    )

    return 1.0 if passed else 0


def _matches(
    actual: Observation,
    expected: Value,
    match: Literal["contains", "exact", "regex"],
    normalize_space: bool,
    case_sensitive: bool,
) -> bool:
    actual_text = _to_text(actual)
    expected_text = _to_text(expected)

    if normalize_space:
        actual_text = _normalize_space(actual_text)
        expected_text = _normalize_space(expected_text)

    if match == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(expected_text, actual_text, flags=flags) is not None

    if not case_sensitive:
        actual_text = actual_text.casefold()
        expected_text = expected_text.casefold()

    if match == "exact":
        return actual_text == expected_text

    return expected_text in actual_text


def _to_text(value: Observation) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_space(value: str) -> str:
    return " ".join(value.split())
