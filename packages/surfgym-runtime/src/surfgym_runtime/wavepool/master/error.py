from fastapi import status
from surfgym_contracts.protocol.upstream_to_gateway import UpstreamErrorType


class MasterError(Exception):
    def __init__(
        self, error_type: UpstreamErrorType, message: str, status_code: int, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.error_type: UpstreamErrorType = error_type
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class OutOfInstanceError(MasterError):
    def __init__(self, message: str):
        super().__init__("OUT_OF_INSTANCE", message, status.HTTP_503_SERVICE_UNAVAILABLE, True)


class UnexpectedError(MasterError):
    def __init__(self, message: str):
        super().__init__("UNEXPECTED", message, status.HTTP_500_INTERNAL_SERVER_ERROR, False)


class InstanceRequestFailed(MasterError):
    def __init__(self, message: str):
        super().__init__(
            "INSTANCE_REQUEST_FAILED",
            message,
            status.HTTP_502_BAD_GATEWAY,
            True,
        )
