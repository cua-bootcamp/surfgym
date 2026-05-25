from fastapi import status
from surfgym_contracts.protocol.upstream_to_gateway import InstanceErrorType


class InstanceError(Exception):
    def __init__(
        self, error_type: InstanceErrorType, message: str, status_code: int, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.error_type: InstanceErrorType = error_type
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class UnexpectedError(InstanceError):
    def __init__(self, message: str):
        super().__init__(
            "INSTANCE_UNEXPECTED", message, status.HTTP_500_INTERNAL_SERVER_ERROR, False
        )


class InstanceNotIdle(InstanceError):
    def __init__(self, message: str) -> None:
        super().__init__("INSTANCE_NOT_IDLE", message, status.HTTP_409_CONFLICT, True)


class InstanceIdle(InstanceError):
    def __init__(self, message: str) -> None:
        super().__init__("INSTANCE_IDLE", message, status.HTTP_409_CONFLICT, False)


class InvalidCommand(InstanceError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_COMMAND", message, status.HTTP_400_BAD_REQUEST, False)


class InvalidInstanceId(InstanceError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_INSTANCE_ID", message, status.HTTP_400_BAD_REQUEST, False)


class CreateFailed(InstanceError):
    def __init__(self, message: str) -> None:
        super().__init__("CREATE_FAILED", message, status.HTTP_500_INTERNAL_SERVER_ERROR, True)
