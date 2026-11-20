class GribError(Exception):
    status_code = 400

    def __init__(self, message: str, extra: dict | None = None):
        super().__init__(message)
        self.message = message
        self.extra = extra or {}


class BadRequest(GribError):
    status_code = 400


class Unauthorized(GribError):
    status_code = 401


class Forbidden(GribError):
    status_code = 403


class NotFound(GribError):
    status_code = 404


class Conflict(GribError):
    status_code = 409


class QueryError(GribError):
    status_code = 400
