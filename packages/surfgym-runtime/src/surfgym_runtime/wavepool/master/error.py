from fastapi import status
from fastapi.responses import JSONResponse
from surfgym_contracts.protocol.master_to_gateway import ErrorResponse, MasterServerErrorType

_status_code_map: dict[MasterServerErrorType, int] = {
    MasterServerErrorType.NO_INSTANCES_AVAILABLE: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MasterServerErrorType.INVALID_PAYLOAD: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def error_response(error_type: MasterServerErrorType, msg: str) -> JSONResponse:
    payload = ErrorResponse(error_type=error_type, message=msg)
    return JSONResponse(
        status_code=_status_code_map.get(error_type, status.HTTP_500_INTERNAL_SERVER_ERROR),
        content=payload.model_dump(),
    )
