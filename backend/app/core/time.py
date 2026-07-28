"""Time helpers for the recruitment-agent backend.

All timestamps are stored in UTC (ratified PR-13 §12). With the Stage 5.1
PR-23 migration every datetime column is now ``TIMESTAMPTZ``, so a
timezone-aware value is the single correct representation. Use
:func:`utcnow_aware` everywhere.

The legacy ``utcnow_naive`` / ``_to_naive_utc`` helpers were removed in
PR-23 (追债项 6): the schema no longer has naive ``TIMESTAMP`` columns, so
normalizing to naive UTC is no longer needed.
"""

from datetime import UTC, datetime


def utcnow_aware() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (``datetime.now(UTC)``).

    Use this for all code — model columns, SSE/event payloads, logging, and
    snapshot comparisons. Naive values are no longer required now that the
    schema is ``TIMESTAMPTZ``-only.
    """
    return datetime.now(UTC)
