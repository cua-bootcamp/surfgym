import time


class SGError(Exception):
    pass


class ConfigError(SGError):
    pass


class SGRetryableError(Exception):
    pass


class OmniboxBusyError(SGRetryableError):
    pass


class OmniBoxTransportError(SGRetryableError):
    pass


class HttpStackOperationTimeoutError(SGRetryableError):
    pass


class OmniboxInvalidScreenshotError(SGRetryableError):
    pass


class DeadlineExceeded(TimeoutError):
    pass


class Deadline:
    def __init__(self, deadline_at: float) -> None:
        self.deadline_at = deadline_at

    def remaining(self) -> float:
        return self.deadline_at - time.monotonic()

    def check(self, context: str) -> None:
        if self.remaining() <= 0:
            raise DeadlineExceeded(f"Gateway request deadline exceeded in {context}")

    def timeout(self, cap: float) -> float:
        remaining = self.remaining()
        if remaining <= 0:
            raise DeadlineExceeded("Gateway request deadline exceeded")
        return min(cap, remaining)
