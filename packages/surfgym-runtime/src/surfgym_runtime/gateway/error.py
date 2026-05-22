import time

from surfgym_contracts.protocol.gateway_to_agent import ErrorType


class GatewayError(Exception):
    def __init__(self, error_type: ErrorType, message: str) -> None:
        super().__init__(message)
        self.error_type: ErrorType = error_type
        self.message = message


class InvalidRequest(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_REQUEST", message)


class DeadlineExceeded(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__("TIMEOUT", message)


class RetryableError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Deadline:
    def __init__(self, deadline_at: float, context: str) -> None:
        self.deadline_at = deadline_at
        self.error = DeadlineExceeded(f"Deadline exceeded in {context}")

    def remaining(self) -> float:
        return self.deadline_at - time.monotonic()

    def check(self) -> None:
        if self.remaining() <= 0:
            raise self.error

    def alarm(self, alarm: float) -> float:
        r = self.remaining()
        if r <= alarm:
            raise self.error
        return r
