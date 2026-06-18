import re
from typing import Literal

from surfgym_contracts.task import Evaluation, Observation, Value


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
    if isinstance(actual, list) or isinstance(expected, list):
        return _matches_list(
            actual,
            expected,
            match=match,
            normalize_space=normalize_space,
            case_sensitive=case_sensitive,
        )

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


def _matches_list(
    actual: Observation,
    expected: Value,
    match: Literal["contains", "exact", "regex"],
    normalize_space: bool,
    case_sensitive: bool,
) -> bool:
    if not isinstance(actual, list) or not isinstance(expected, list):
        return False

    actual_values = [
        _normalize_match_text(
            value,
            normalize_space=normalize_space,
            case_sensitive=case_sensitive,
        )
        for value in actual
    ]
    expected_values = [
        _normalize_match_text(
            value,
            normalize_space=normalize_space,
            case_sensitive=case_sensitive,
        )
        for value in expected
    ]

    if match == "exact":
        return actual_values == expected_values

    if match == "contains":
        return all(value in actual_values for value in expected_values)

    if match == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        return all(
            any(
                re.search(expected_pattern, actual_value, flags=flags)
                for actual_value in actual_values
            )
            for expected_pattern in expected_values
        )

    return False


def _to_text(value: Observation) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _normalize_match_text(
    value: str,
    normalize_space: bool,
    case_sensitive: bool,
) -> str:
    text = value
    if normalize_space:
        text = _normalize_space(text)
    if not case_sensitive:
        text = text.casefold()
    return text
