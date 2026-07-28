"""migrate naive timestamps to TIMESTAMPTZ (PR-23 · 追债项 6)

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-07-28

Background
----------
Per repo convention every naive ``TIMESTAMP`` value is stored in UTC
(``utcnow_naive()`` semantics, ratified in PR-13 §12). This migration
promotes 28 columns across 11 tables from ``TIMESTAMP WITHOUT TIME ZONE``
to ``TIMESTAMPTZ``, converting each value with ``<col> AT TIME ZONE 'UTC'``
(interpret the naive value as UTC). ``func.now()`` defaults are untouched
and remain compatible (``now()`` already returns ``TIMESTAMPTZ``).

Reversible: downgrade strips the tz back to naive UTC with the symmetric
``AT TIME ZONE 'UTC'`` expression.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | None = None
depends_on: str | None = None

# (table, column) pairs — 28 columns across 11 tables.
# TimestampMixin contributes {created_at, updated_at} to 9 tables;
# the rest are standalone columns.
COLUMNS: list[tuple[str, str]] = [
    # TimestampMixin (9 tables)
    ("tasks", "created_at"),
    ("tasks", "updated_at"),
    ("skills", "created_at"),
    ("skills", "updated_at"),
    ("resumes", "created_at"),
    ("resumes", "updated_at"),
    ("match_scores", "created_at"),
    ("match_scores", "updated_at"),
    ("jd_templates", "created_at"),
    ("jd_templates", "updated_at"),
    ("jds", "created_at"),
    ("jds", "updated_at"),
    ("executions", "created_at"),
    ("executions", "updated_at"),
    ("candidate_status_history", "created_at"),
    ("candidate_status_history", "updated_at"),
    ("candidate_notes", "created_at"),
    ("candidate_notes", "updated_at"),
    # standalone columns
    ("skill_versions", "created_at"),
    ("skill_versions", "published_at"),
    ("skill_execution_logs", "executed_at"),
    ("tasks", "started_at"),
    ("tasks", "finished_at"),
    ("executions", "started_at"),
    ("executions", "finished_at"),
    ("match_scores", "resume_updated_at_snapshot"),
    ("match_scores", "jd_updated_at_snapshot"),
    ("candidate_status_history", "occurred_at"),
]


def upgrade() -> None:
    for table, col in COLUMNS:
        op.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
            )
        )


def downgrade() -> None:
    for table, col in reversed(COLUMNS):
        op.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE TIMESTAMP WITHOUT TIME ZONE USING {col} AT TIME ZONE 'UTC'"
            )
        )
