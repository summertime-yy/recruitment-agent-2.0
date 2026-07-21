"""Time helpers for the recruitment-agent backend.

NOTE ON ``utcnow_naive``
-----------------------
``utcnow_naive`` exists ONLY to satisfy a *historical DB constraint*: several
columns in the schema are ``TIMESTAMP WITHOUT TIME ZONE`` (naive), and the
asyncpg driver refuses to write timezone-aware datetimes into them. Keep using
``utcnow_naive`` for those legacy write paths.

This is NOT a new convention. New code that does NOT touch those naive columns
should use ``utcnow_aware`` (``datetime.now(timezone.utc)``), per the repo
guidance in AGENTS.md ("use ``datetime.now(timezone.utc)`` in new code").
"""

from datetime import UTC, datetime


def utcnow_aware() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (``datetime.now(timezone.utc)``).

    Use this for new code, SSE/event payloads, logging, and any value that is
    NOT written directly into a ``TIMESTAMP WITHOUT TIME ZONE`` column.
    """
    return datetime.now(UTC)


def utcnow_naive() -> datetime:
    """Return a naive UTC ``datetime`` for writing into naive DB columns.

    LEGACY CONSTRAINT ONLY. The schema has ``TIMESTAMP WITHOUT TIME ZONE``
    columns that cannot accept tz-aware values. Do not use this for new
    business logic — prefer :func:`utcnow_aware`.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Normalize a datetime to a naive UTC value for safe comparison.

    Accepts tz-aware or naive datetimes (or ``None``). Guards against
    mixed aware/naive comparisons that would otherwise raise ``TypeError``.
    Intended for legacy read/compare paths against naive DB columns — not
    for new business logic.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)
