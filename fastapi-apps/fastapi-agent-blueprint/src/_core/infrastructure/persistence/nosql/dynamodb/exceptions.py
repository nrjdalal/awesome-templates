from src._core.exceptions.base_exception import BaseCustomException


class DynamoDBException(BaseCustomException):
    """Base exception for DynamoDB operations."""

    pass


class DynamoDBNotFoundException(DynamoDBException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            message="Requested item not found",
            error_code="DYNAMODB_NOT_FOUND",
        )


class DynamoDBConditionFailedException(DynamoDBException):
    def __init__(self, message: str = "Condition check failed") -> None:
        super().__init__(
            status_code=409,
            message=message,
            error_code="DYNAMODB_CONDITION_FAILED",
        )


class DynamoDBThrottlingException(DynamoDBException):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            message="DynamoDB throughput exceeded",
            error_code="DYNAMODB_THROTTLED",
        )


class DynamoDBBatchIncompleteException(DynamoDBException):
    """A batch finished with items DynamoDB never accepted (#329 F6).

    Distinct from :class:`DynamoDBThrottlingException` on purpose. Throttling is
    the usual cause of ``UnprocessedItems`` but not the only one, and naming the
    cause would be a guess.

    503, not 429: 429 asserts the *client* is sending too fast, which we do not
    know. An unprocessed batch after retries is a retryable backend failure of
    unknown cause, which is what 503 means. It also crosses the
    ``NOTIFICATION_SEVERITY_THRESHOLD`` (500), so a batch that cannot complete
    pages an operator — correct here, unlike a client-side capability mismatch.

    The table name is **not** in the message. ``custom_exception_handler``
    returns the message verbatim to the client, and ``DynamoDBClient``
    deliberately keeps table and account identifiers out of responses (see its
    comment on the AWS ``Error.Message`` policy). The name goes to structlog at
    the raise site instead.

    Note what the count is and is not: it tells a caller *how much* did not land,
    not *which* items. Identifying them means re-reading or re-submitting the
    batch; the count exists so the failure is measurable, not so it is
    individually repairable.

    Raised rather than returning a partial result. For writes that is the only
    safe answer — the previous behaviour built a success DTO for every item in
    the chunk, so a caller committed to writes that were not in the table. For
    reads it discards successful work in the same call, which is the accepted
    trade: reads are idempotent and cheap to redo, while a silently short list is
    indistinguishable from "those keys do not exist" and cannot be detected at
    all.
    """

    def __init__(self, operation: str, unprocessed_count: int):
        super().__init__(
            status_code=503,
            message=(
                f"DynamoDB {operation} left {unprocessed_count} item(s) "
                "unprocessed after exhausting retries"
            ),
            error_code="DYNAMODB_BATCH_INCOMPLETE",
        )


class DynamoDBInvalidCursorException(DynamoDBException):
    """A pagination cursor that did not survive decoding (#329).

    The token is client-supplied, so a raw ``binascii.Error`` /
    ``JSONDecodeError`` / ``UnicodeDecodeError`` escaping as a 500 is both the
    wrong status and — since #17 — an operator page for a malformed request.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            message="Malformed pagination cursor",
            error_code="DYNAMODB_INVALID_CURSOR",
        )


class DynamoDBInvalidLimitException(DynamoDBException):
    """A pagination bound DynamoDB will not accept (#329 F11).

    ``query_items`` is reachable from adopter request paths, and a bare
    ``ValueError`` there is turned into ``INTERNAL_SERVER_ERROR`` by the generic
    handler — a 500 plus an operator page for what is a malformed request. The
    first fix for F11 made exactly that mistake: it stopped ``limit=0`` from
    being silently dropped and started returning a 500 instead.
    """

    def __init__(self, limit: int) -> None:
        super().__init__(
            status_code=400,
            message=(
                f"limit must be >= 1 when provided (got {limit}); "
                "omit it for an unbounded query"
            ),
            error_code="DYNAMODB_INVALID_LIMIT",
        )
