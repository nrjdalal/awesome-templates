class BaseCustomException(Exception):
    def __init__(
        self,
        status_code: int = 400,
        message: str = "Not Found",
        error_code: str = "CUSTOM_ERROR",
        details: dict | None = None,
    ):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.details = details

    def __str__(self):
        return f"{self.status_code} [{self.error_code}]: {self.message}"
