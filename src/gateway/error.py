import time


class WebGymRLError(Exception):
    pass


class ConfigError(WebGymRLError):
    pass


class WebGymEnvRetryableError(Exception):
    pass


class OmniboxBusyError(WebGymEnvRetryableError):
    pass


class OmniBoxTransportError(WebGymEnvRetryableError):
    pass


class HttpStackOperationTimeoutError(WebGymEnvRetryableError):
    pass


class OmniboxInvalidScreenshotError(WebGymEnvRetryableError):
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
