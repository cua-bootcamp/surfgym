from fastapi import status


class MasterError(Exception):
    def __init__(self, message: str, status_code: int, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class OutOfInstanceError(MasterError):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE, True)


class UnexpectedError(MasterError):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, False)


class InstanceRequestFailed(MasterError):
    def __init__(self, message: str):
        super().__init__(
            message,
            status.HTTP_502_BAD_GATEWAY,
            True,
        )
