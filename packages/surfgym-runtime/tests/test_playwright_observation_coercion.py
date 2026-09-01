import asyncio

from surfgym_contracts.task import ConsoleCriteria
from surfgym_runtime.wavepool.instance.service import (
    _coerce_playwright_observation,
    _eval_console_observation,
)


def test_console_observation_preserves_nested_json_nulls() -> None:
    payload = {
        "initial_state": {
            "items": [None, {"caption": None}],
            "selected": None,
        },
        "current_state": {"items": [None]},
    }

    class Page:
        async def evaluate(self, _script: str) -> object:
            return payload

    criteria = ConsoleCriteria(value=None, script="() => ({})")

    assert asyncio.run(_eval_console_observation(criteria, Page(), 7)) == (payload, 7)


def test_observation_still_rejects_nested_non_json_values() -> None:
    assert _coerce_playwright_observation({"value": [object()]}) is None
