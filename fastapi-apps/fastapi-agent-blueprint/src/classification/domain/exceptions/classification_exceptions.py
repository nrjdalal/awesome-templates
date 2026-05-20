from src._core.exceptions.base_exception import BaseCustomException


class ClassificationFailedException(BaseCustomException):
    def __init__(self, detail: str = "") -> None:
        msg = f"Classification failed: {detail}" if detail else "Classification failed"
        super().__init__(
            status_code=500,
            message=msg,
            error_code="CLASSIFICATION_FAILED",
        )
