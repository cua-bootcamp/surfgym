import time
from collections.abc import Callable

from surfgym_contracts.protocol.gateway_to_agent import ErrorType


class GatewayError(Exception):
    def __init__(self, error_type: ErrorType, message: str) -> None:
        super().__init__(message)
        self.error_type: ErrorType = error_type
        self.message = message


class InvalidRequest(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_REQUEST", message)


class UpstreamError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__("UPSTREAM", message)


class DeadlineExceeded(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__("TIMEOUT", message)


class RetryableError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Deadline:
    def __init__(self, expires_at: float, context: str) -> None:
        self.expires_at = expires_at
        self.error = DeadlineExceeded(f"Deadline exceeded in {context}")

    def remaining(self) -> float:
        return self.expires_at - time.monotonic()

    def check(self) -> None:
        if self.remaining() <= 0:
            raise self.error

    def require_remaining(self, required: float) -> None:
        if self.remaining() <= required:
            raise self.error

    def timeout_for(self, max_timeout: float) -> float:
        remaining = self.remaining()
        if remaining <= 0:
            raise self.error
        return min(max_timeout, remaining)


def deadline_for(deadline_at: float) -> Callable[[str], Deadline]:
    return lambda context: Deadline(deadline_at, context)
