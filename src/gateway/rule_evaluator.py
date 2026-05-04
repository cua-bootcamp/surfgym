from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

from src.protocol.instance_to_gateway import (
    ElementSnapshot,
    PageSnapshot,
)


@dataclass(frozen=True)
class RuleCheck:
    passed: bool
    message: str


Rule: TypeAlias = dict[str, Any]


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


def collect_selectors(evaluation: Any) -> list[str]:
    selectors: list[str] = []
    for rule in _rules(evaluation):
        selector = rule.get("selector")
        if isinstance(selector, str) and selector and selector not in selectors:
            selectors.append(selector)
    return selectors


def uses_page_html(evaluation: Any) -> bool:
    for rule in _rules(evaluation):
        if "selector" not in rule and ("html" in rule or "html_regex" in rule):
            return True
    return False


def evaluate_page_rules(evaluation: Any, snapshot: PageSnapshot) -> EvaluationResult:
    rules = _rules(evaluation)
    if not rules:
        return EvaluationResult(False, (RuleCheck(False, "no evaluation rules configured"),))

    mode = "all"
    evaluation_rule = _as_rule(cast(object, evaluation))
    if evaluation_rule is not None:
        raw_mode = _get_first_rule_value(evaluation_rule, ("mode", "operator"), "all")
        mode = str(raw_mode).lower()

    if mode not in {"all", "any"}:
        raise ValueError(f"Unsupported evaluation mode: {mode}")

    checks = tuple(_evaluate_rule(rule, snapshot, index) for index, rule in enumerate(rules, 1))
    passed = (
        all(check.passed for check in checks)
        if mode == "all"
        else any(check.passed for check in checks)
    )
    return EvaluationResult(passed, checks)


def _rules(evaluation: Any) -> list[Rule]:
    if evaluation is None:
        return []

    if isinstance(evaluation, list):
        return _collect_rules(cast(list[object], evaluation))

    rule = _as_rule(cast(object, evaluation))
    if rule is None:
        return []

    raw_rules = _get_rule_value(rule, "rules")
    if isinstance(raw_rules, list):
        return _collect_rules(cast(list[object], raw_rules))

    if any(key in rule for key in _RULE_KEYS):
        return [rule]

    return []


def _as_rule(value: object) -> Rule | None:
    if not isinstance(value, dict):
        return None

    raw_rule = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_rule):
        return None

    return cast(Rule, raw_rule)


def _collect_rules(values: list[object]) -> list[Rule]:
    rules: list[Rule] = []
    for value in values:
        rule = _as_rule(value)
        if rule is not None:
            rules.append(rule)
    return rules


_RULE_KEYS = {
    "selector",
    "text",
    "text_regex",
    "html",
    "html_regex",
    "url",
    "url_regex",
    "title",
    "title_regex",
    "attribute",
    "attr",
}


def _evaluate_rule(rule: Rule, snapshot: PageSnapshot, index: int) -> RuleCheck:
    selector = rule.get("selector")
    if isinstance(selector, str) and selector:
        return _evaluate_selector_rule(rule, snapshot, selector, index)
    return _evaluate_page_rule(rule, snapshot, index)


def _evaluate_selector_rule(
    rule: Rule,
    snapshot: PageSnapshot,
    selector: str,
    index: int,
) -> RuleCheck:
    if selector in snapshot.selector_errors:
        return RuleCheck(False, f"rule {index}: invalid selector {selector!r}")

    elements = snapshot.elements.get(selector, [])

    visible_filter = rule.get("visible")
    if visible_filter is not None:
        expected_visible = bool(visible_filter)
        elements = [element for element in elements if element.visible == expected_visible]

    if not elements:
        return RuleCheck(False, f"rule {index}: no matching elements for selector {selector!r}")

    if not _has_content_condition(rule):
        return RuleCheck(True, f"rule {index}: selector {selector!r} exists")

    for element in elements:
        if _element_satisfies(rule, element):
            return RuleCheck(True, f"rule {index}: selector {selector!r} matched")

    return RuleCheck(False, f"rule {index}: selector {selector!r} did not satisfy content rule")


def _evaluate_page_rule(
    rule: Rule,
    snapshot: PageSnapshot,
    index: int,
) -> RuleCheck:
    if "url" in rule:
        passed = _matches(snapshot.url, rule["url"], rule, normalize_space=False)
        return RuleCheck(passed, _message(index, "url", passed))
    if "url_regex" in rule:
        passed = _matches(snapshot.url, rule["url_regex"], rule, match="regex")
        return RuleCheck(passed, _message(index, "url_regex", passed))
    if "title" in rule:
        passed = _matches(snapshot.title, rule["title"], rule)
        return RuleCheck(passed, _message(index, "title", passed))
    if "title_regex" in rule:
        passed = _matches(snapshot.title, rule["title_regex"], rule, match="regex")
        return RuleCheck(passed, _message(index, "title_regex", passed))
    if "html" in rule:
        passed = _matches(snapshot.html, rule["html"], rule, normalize_space=False)
        return RuleCheck(passed, _message(index, "html", passed))
    if "html_regex" in rule:
        passed = _matches(
            snapshot.html,
            rule["html_regex"],
            rule,
            match="regex",
            normalize_space=False,
        )
        return RuleCheck(passed, _message(index, "html_regex", passed))
    if "text_regex" in rule:
        passed = _matches(snapshot.text, rule["text_regex"], rule, match="regex")
        return RuleCheck(passed, _message(index, "text_regex", passed))
    if "text" in rule:
        passed = _matches(snapshot.text, rule["text"], rule)
        return RuleCheck(passed, _message(index, "text", passed))

    return RuleCheck(False, f"rule {index}: unsupported rule shape")


def _element_satisfies(rule: Rule, element: ElementSnapshot) -> bool:
    conditions: list[bool] = []

    if "text" in rule:
        conditions.append(_matches(element.text, rule["text"], rule))
    if "text_regex" in rule:
        conditions.append(_matches(element.text, rule["text_regex"], rule, match="regex"))
    if "html" in rule:
        conditions.append(_matches(element.html, rule["html"], rule, normalize_space=False))
    if "html_regex" in rule:
        conditions.append(
            _matches(
                element.html,
                rule["html_regex"],
                rule,
                match="regex",
                normalize_space=False,
            )
        )

    attribute_name = _get_first_rule_value(rule, ("attribute", "attr"))
    if isinstance(attribute_name, str) and attribute_name:
        actual = element.attributes.get(attribute_name, "")

        if not actual and hasattr(element, attribute_name):
            actual = str(getattr(element, attribute_name))

        expected = _get_first_rule_value(rule, ("value", "attr_value"), "")
        conditions.append(_matches(actual, expected, rule))

    return bool(conditions) and all(conditions)


def _has_content_condition(rule: Rule) -> bool:
    return any(
        key in rule
        for key in (
            "text",
            "text_regex",
            "html",
            "html_regex",
            "attribute",
            "attr",
        )
    )


def _matches(
    actual: Any,
    expected: Any,
    rule: Rule,
    *,
    match: str | None = None,
    normalize_space: bool | None = None,
) -> bool:
    if isinstance(expected, list):
        options = cast(list[Any], expected)
        return any(
            _matches(actual, option, rule, match=match, normalize_space=normalize_space)
            for option in options
        )

    actual_text = "" if actual is None else str(actual)
    expected_text = "" if expected is None else str(expected)

    raw_match = match if match is not None else _get_rule_value(rule, "match", "contains")
    match_mode = str(raw_match).lower()
    if match_mode not in {"contains", "exact", "regex"}:
        raise ValueError(f"Unsupported match mode: {match_mode}")

    if normalize_space is None:
        normalize_space = bool(_get_rule_value(rule, "normalize_space", True))
    if normalize_space:
        actual_text = _normalize_space(actual_text)
        expected_text = _normalize_space(expected_text)

    case_sensitive = bool(_get_rule_value(rule, "case_sensitive", False))
    if match_mode == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(expected_text, actual_text, flags=flags) is not None

    if not case_sensitive:
        actual_text = actual_text.casefold()
        expected_text = expected_text.casefold()

    if match_mode == "exact":
        return actual_text == expected_text
    return expected_text in actual_text


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _message(index: int, target: str, passed: bool) -> str:
    status = "matched" if passed else "did not match"
    return f"rule {index}: {target} {status}"


def _get_rule_value(rule: Rule, key: str, default: Any = None) -> Any:
    return rule[key] if key in rule else default


def _get_first_rule_value(rule: Rule, keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in rule:
            return rule[key]
    return default
