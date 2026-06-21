import os
from collections.abc import Sequence
from typing import Any, cast
from urllib.parse import urlparse

import requests
from surfgym_contracts import Website

_DEFAULT_RESET_TIMEOUT = 15.0


# Allocation
def post_reset_daemon(
    *,
    websites: Sequence[Website],
    payload: dict[str, object],
    timeout_env: str | None = None,
    app_name: str = "App",
) -> None:
    reset_url = derive_reset_url(websites)
    timeout = _reset_timeout(timeout_env)

    try:
        response = requests.post(
            reset_url,
            json=cast(Any, payload),
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"{app_name} reset daemon timed out after {timeout:g}s: {reset_url}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"{app_name} reset daemon request failed: url={reset_url} error={type(exc).__name__}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"{app_name} reset daemon failed: "
            f"status={response.status_code} body={_response_text(response)}"
        )

    try:
        body: object = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"{app_name} reset daemon returned invalid JSON: {_response_text(response)}"
        ) from exc

    if not isinstance(body, dict) or cast(dict[str, object], body).get("ok") is not True:
        raise RuntimeError(f"{app_name} reset daemon failed: response={body!r}")


def derive_reset_url(websites: Sequence[Website]) -> str:
    if not websites:
        raise RuntimeError("App reset requires at least one website URL.")

    parsed = urlparse(websites[0].url)
    host = parsed.hostname
    port = parsed.port
    if not host:
        raise RuntimeError(f"App GUI URL must include a host: {websites[0].url}")
    if port is None:
        raise RuntimeError(f"App GUI URL must include a port: {websites[0].url}")

    netloc = f"[{host}]:{port + 1}" if ":" in host else f"{host}:{port + 1}"
    return f"http://{netloc}/reset"


def _reset_timeout(timeout_env: str | None) -> float:
    timeout = _env_float("SURFGYM_APP_RESET_TIMEOUT", _DEFAULT_RESET_TIMEOUT)
    if timeout_env is not None:
        timeout = _env_float(timeout_env, timeout)
    return timeout


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float, got {value!r}") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return parsed


def _response_text(response: requests.Response) -> str:
    text = response.text.strip()
    if not text:
        return "empty response"
    return " ".join(text.split())[:2000]
