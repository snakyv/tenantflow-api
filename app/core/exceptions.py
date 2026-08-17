from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = 400


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code=code, message=message, status_code=404)


class ForbiddenError(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "Operation is not allowed") -> None:
        super().__init__(code=code, message=message, status_code=403)


class ConflictError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code=code, message=message, status_code=409)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(code="AUTHENTICATION_FAILED", message=message, status_code=401)
