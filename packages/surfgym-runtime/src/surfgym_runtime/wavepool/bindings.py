"""Pure, internal lifecycle binding helpers."""

from __future__ import annotations

import uuid


def web_cleanup_cookie(context_id: str, origin: str, cookie_name: str) -> str:
    """Return the stable per-context cookie for one declared web reset binding."""
    name = f"surfgym-server-reset\x1f{context_id}\x1f{origin.rstrip('/')}\x1f{cookie_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
