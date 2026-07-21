"""add candidate tags source dedup and notes

Revision ID: 113702a6d427
Revises: f8a2c4e91b03
Create Date: 2026-07-14 18:03:59.715647

Stage 3 扩展：
- resumes 新增 tags(JSONB) / source / duplicate_of_resume_id / dedup_status
- 新建 candidate_notes 表（备注/评价）
- 保留已有 ix_resumes_candidate_status 索引（autogenerate 误判为需删除，实际应保留）
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "113702a6d427"
down_revision: str = "f8a2c4e91b03"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 新建候选人备注/评价表
    op.create_table(
        "candidate_notes",
        sa.Column("note_id", sa.String(length=50), nullable=False),
        sa.Column("resume_id", sa.String(length=50), nullable=False),
        sa.Column(
            "note_type",
            sa.String(length=20),
            server_default="NOTE",
            nullable=False,
            comment="类型：NOTE=备注，EVALUATION=评价",
        ),
        sa.Column("content", sa.String(length=2000), nullable=False, comment="备注/评价内容"),
        sa.Column("rating", sa.Integer(), nullable=True, comment="评分1-5（仅EVALUATION类型使用）"),
        sa.Column("author", sa.String(length=50), nullable=True, comment="作者/操作人ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.resume_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("note_id"),
    )
    op.create_index(op.f("ix_candidate_notes_resume_id"), "candidate_notes", ["resume_id"], unique=False)

    # resumes 扩展候选人管理字段
    op.add_column(
        "resumes",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="候选人标签列表（自由文本标签，如 高潜/技术/管理）",
        ),
    )
    op.add_column(
        "resumes",
        sa.Column("source", sa.String(length=50), nullable=True, comment="来源渠道：BOSS/拉勾/内推/猎头/邮件 等"),
    )
    op.add_column(
        "resumes",
        sa.Column(
            "duplicate_of_resume_id",
            sa.String(length=50),
            nullable=True,
            comment="疑似重复的源简历ID（候选人级去重，硬匹配命中后填入）",
        ),
    )
    op.add_column(
        "resumes",
        sa.Column(
            "dedup_status",
            sa.String(length=20),
            server_default="NONE",
            nullable=False,
            comment="去重状态：NONE/SUSPECTED/CONFIRMED_DUP/IGNORED",
        ),
    )
    op.create_foreign_key(
        "fk_resumes_duplicate_of_resume_id",
        "resumes",
        "resumes",
        ["duplicate_of_resume_id"],
        ["resume_id"],
        ondelete="SET NULL",
    )

    # 为去重状态和来源加索引，便于列表筛选
    op.create_index("ix_resumes_dedup_status", "resumes", ["dedup_status"], unique=False)
    op.create_index("ix_resumes_source", "resumes", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_resumes_source", table_name="resumes")
    op.drop_index("ix_resumes_dedup_status", table_name="resumes")
    op.drop_constraint("fk_resumes_duplicate_of_resume_id", "resumes", type_="foreignkey")
    op.drop_column("resumes", "dedup_status")
    op.drop_column("resumes", "duplicate_of_resume_id")
    op.drop_column("resumes", "source")
    op.drop_column("resumes", "tags")
    op.drop_index(op.f("ix_candidate_notes_resume_id"), table_name="candidate_notes")
    op.drop_table("candidate_notes")
