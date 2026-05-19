from fastapi import status
from fastapi.responses import JSONResponse
from surfgym_contracts.protocol.instance_to_gateway import ErrorResponse, InstanceServerErrorType

_status_code_map: dict[InstanceServerErrorType, int] = {
    InstanceServerErrorType.INSTANCE_NOT_IDLE: status.HTTP_500_INTERNAL_SERVER_ERROR,
    InstanceServerErrorType.INSTANCE_IDLE: status.HTTP_500_INTERNAL_SERVER_ERROR,
    InstanceServerErrorType.INVALID_COMMAND: status.HTTP_400_BAD_REQUEST,
    InstanceServerErrorType.INVALID_INSTANCE_ID: status.HTTP_400_BAD_REQUEST,
    InstanceServerErrorType.CREATE_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def error_response(error_type: InstanceServerErrorType, msg: str) -> JSONResponse:
    payload = ErrorResponse(error_type=error_type, message=msg)
    return JSONResponse(
        status_code=_status_code_map.get(error_type, status.HTTP_500_INTERNAL_SERVER_ERROR),
        content=payload.model_dump(),
    )
