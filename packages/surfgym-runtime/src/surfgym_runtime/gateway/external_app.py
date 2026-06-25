from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlparse

import requests
from surfgym_contracts.task import ExternalApp, Website

from surfgym_runtime.gateway.error import InvalidRequest, UpstreamError


@dataclass(frozen=True)
class ExternalAppSession:
    app: ExternalApp
    session_id: int
    control_origin: str


class ExternalAppGatewayClient:
    def prepare_websites(
        self,
        websites: list[Website],
        *,
        app: ExternalApp,
        session_id: int,
    ) -> tuple[ExternalAppSession, list[Website]]:
        if not websites:
            raise InvalidRequest("External app task requires at least one website URL.")

        session = ExternalAppSession(
            app=app,
            session_id=session_id,
            control_origin=_derive_control_origin(websites[0].url),
        )
        return session, [_with_session_path(website, session_id) for website in websites]

    def reset(self, session: ExternalAppSession, timeout: float) -> None:
        self._post(session, "reset", timeout)

    def release(self, session: ExternalAppSession, timeout: float) -> None:
        self._post(session, "release", timeout)

    def _post(
        self,
        session: ExternalAppSession,
        action: Literal["reset", "release"],
        timeout: float,
    ) -> None:
        url = _control_url(session, action)

        try:
            response = requests.post(url, timeout=timeout)
        except requests.exceptions.Timeout as exc:
            raise UpstreamError(
                f"External app gateway timed out: action={action} url={url}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise UpstreamError(
                f"External app gateway request failed: "
                f"action={action} url={url} error={type(exc).__name__}"
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise UpstreamError(
                f"External app gateway failed: action={action} "
                f"status={response.status_code} url={url} body={_response_text(response)}"
            )

        try:
            body: object = response.json()
        except ValueError:
            return

        if isinstance(body, dict) and cast(dict[str, object], body).get("ok") is False:
            raise UpstreamError(
                f"External app gateway reported failure: action={action} url={url} body={body!r}"
            )


def _with_session_path(website: Website, session_id: int) -> Website:
    return Website(
        website_id=website.website_id,
        url=f"{website.url.rstrip('/')}/sessions/{session_id}/",
    )


def _derive_control_origin(serving_url: str) -> str:
    parsed = urlparse(serving_url)
    host = parsed.hostname
    port = parsed.port

    if not host:
        raise InvalidRequest(f"External app serving URL must include a host: {serving_url}")
    if port is None:
        raise InvalidRequest(f"External app serving URL must include a port: {serving_url}")

    netloc = f"[{host}]:{port + 1}" if ":" in host else f"{host}:{port + 1}"
    return f"http://{netloc}"


def _control_url(
    session: ExternalAppSession,
    action: Literal["reset", "release"],
) -> str:
    return f"{session.control_origin}/{session.app}/sessions/{session.session_id}/{action}"


def _response_text(response: requests.Response) -> str:
    text = response.text.strip()
    if not text:
        return "empty response"
    return " ".join(text.split())[:2000]
