"""add candidate status flow

Revision ID: f8a2c4e91b03
Revises: d5bc93d93eb1
Create Date: 2026-07-14 14:00:00.000000

Stage 3 - 候选人状态流转模块：
- resumes 表新增 candidate_status 列（默认 NEW）
- 新增 candidate_status_history 表，记录状态流转历史
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a2c4e91b03"
down_revision: str | None = "d5bc93d93eb1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) resumes 新增 candidate_status
    op.add_column(
        "resumes",
        sa.Column(
            "candidate_status",
            sa.String(length=30),
            nullable=False,
            server_default="NEW",
            comment="候选人招聘状态：NEW/SCREENING_PASSED/SCREENING_REJECTED/INTERVIEWING/OFFERED/ARCHIVED",
        ),
    )
    op.create_index(
        "ix_resumes_candidate_status", "resumes", ["candidate_status"]
    )

    # 2) candidate_status_history 表
    op.create_table(
        "candidate_status_history",
        sa.Column("history_id", sa.String(length=50), nullable=False),
        sa.Column("resume_id", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("operator", sa.String(length=50), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.resume_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index(
        "ix_candidate_status_history_resume_id",
        "candidate_status_history",
        ["resume_id"],
    )
    op.create_index(
        "ix_candidate_status_history_occurred_at",
        "candidate_status_history",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_status_history_occurred_at", table_name="candidate_status_history")
    op.drop_index("ix_candidate_status_history_resume_id", table_name="candidate_status_history")
    op.drop_table("candidate_status_history")
    op.drop_index("ix_resumes_candidate_status", table_name="resumes")
    op.drop_column("resumes", "candidate_status")
