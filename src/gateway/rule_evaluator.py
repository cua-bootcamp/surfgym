from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from src.gateway.task_store import Evaluation, Rule


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ObservationRequest(FrozenBaseModel):
    id: int
    website_id: str
    target: Literal["text", "html", "url", "title", "attr"]
    selector: Optional[str]
    attr: Optional[str]


def collect_observation_requests(evaluation: Evaluation) -> list[ObservationRequest]:
    return [
        ObservationRequest(
            id=rule_id,
            website_id=rule.website_id,
            target=rule.target,
            selector=rule.selector,
            attr=rule.attr,
        )
        for rule_id, rule in evaluation.rules.items()
    ]


@dataclass(frozen=True)
class RuleCheck:
    passed: bool
    message: str


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    checks: tuple[RuleCheck, ...]

    @property
    def reward(self) -> float:
        return 1.0 if self.passed else 0.0

    def summary(self) -> str:
        if not self.checks:
            return "no evaluation rules"
        return "; ".join(check.message for check in self.checks)


def evaluate_page_rules(
    evaluation: Evaluation,
    snapshot: dict[int, str],
) -> EvaluationResult:
    checks = tuple(
        _evaluate_rule(rule_id, rule, snapshot) for rule_id, rule in evaluation.rules.items()
    )

    passed = (
        all(check.passed for check in checks)
        if evaluation.operator == "and"
        else any(check.passed for check in checks)
    )

    return EvaluationResult(passed=passed, checks=checks)


def _evaluate_rule(
    rule_id: int,
    rule: Rule,
    snapshot: dict[int, str],
) -> RuleCheck:
    if rule_id not in snapshot:
        return RuleCheck(False, f"rule {rule_id}: observation missing")

    actual = snapshot[rule_id]
    passed = _matches(
        actual=actual,
        expected=rule.value,
        match=rule.match,
        normalize_space=rule.normalize_space,
        case_sensitive=rule.case_sensitive,
    )

    target = _describe_rule_target(rule)
    status = "matched" if passed else "did not match"
    return RuleCheck(passed, f"rule {rule_id}: {target} {status}")


def _describe_rule_target(rule: Rule) -> str:
    if rule.selector is not None:
        if rule.target == "attr":
            return f"{rule.selector!r} attr {rule.attr!r}"
        return f"{rule.selector!r} {rule.target}"
    return rule.target


def _matches(
    *,
    actual: str,
    expected: str,
    match: Literal["contains", "exact", "regex"],
    normalize_space: bool,
    case_sensitive: bool,
) -> bool:
    actual_text = actual
    expected_text = expected

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


def _normalize_space(value: str) -> str:
    return " ".join(value.split())
