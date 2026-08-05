from src._core.exceptions.base_exception import BaseCustomException


class InMemoryVectorException(BaseCustomException):
    """Base exception for the in-memory vector store."""

    pass


class VectorFilterUnsupportedException(InMemoryVectorException):
    """A filter operator this backend does not implement (#328 F10).

    A curated 400 rather than a bare ``NotImplementedError``. The filter dict
    reaches the store straight from ``POST /v1/docs/query`` (`QueryRequest.filters`
    is an open ``dict[str, Any]`` described as "S3-Vectors-compatible"), so an
    untranslated exception becomes a generic 500 — and a filter that is valid
    against the S3 backend would then return 200 or 500 depending purely on which
    backend the deployment selected.

    400, not 5xx: the request is the actionable thing, the caller can change the
    filter, and a 5xx would also page an operator through ``ErrorNotifier``
    (severity threshold 500) for what is a client-side capability mismatch.

    ``details`` carries the offending operators and the supported subset so the
    caller learns what to send instead without reading the source.
    """

    def __init__(
        self, unsupported: list[str], supported: list[str], field: str | None = None
    ):
        target = f" on field '{field}'" if field else ""
        super().__init__(
            status_code=400,
            message=(
                f"In-memory vector store does not support "
                f"{sorted(unsupported)}{target}. Supported: {sorted(supported)}"
            ),
            error_code="VECTOR_FILTER_UNSUPPORTED",
        )
