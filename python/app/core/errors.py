from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(self, status_code: int, code: int, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


INVALID_PHASE = lambda: AppError(400, 4001, "INVALID_PHASE")
FORBIDDEN = lambda: AppError(403, 4003, "FORBIDDEN")
NOT_FOUND = lambda: AppError(404, 4004, "NOT_FOUND")
BAD_REQUEST = lambda msg: AppError(400, 4000, msg)
