"""add agent tasks and executions tables

Revision ID: a5b6c7d8e9f0
Revises: e4c1a2b3d4f5
Create Date: 2026-07-20 10:00:00.000000

Stage 5 PR-10 S5-01：落地 tasks / executions 两表
- tasks.task_id 默认 task_{uuid4_hex_12}，复合索引 idx_tasks_status_created(status, created_at DESC)
- executions.task_id FK→tasks.task_id ON DELETE CASCADE，复合索引
  idx_executions_task_created(task_id, created_at ASC) + idx_executions_step_id(step_id)
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: str = "e4c1a2b3d4f5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(length=50), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column(
            "task_type",
            sa.String(length=50),
            nullable=True,
            comment="MATCH_SCORE/MERGE_CANDIDATES/PROFILE_CANDIDATE/GENERATE_JD/GENERAL_QA/UNKNOWN",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
            comment="状态机（Q2，含 CANCELLED）",
        ),
        sa.Column("plan", sa.JSON(), nullable=True, comment="Plan 对象（§3.4）"),
        sa.Column("context", sa.JSON(), nullable=True, comment="{ jd_id?, candidate_ids? }"),
        sa.Column("result", sa.JSON(), nullable=True, comment="最终/部分产物 artifacts"),
        sa.Column("error", sa.JSON(), nullable=True, comment="{ code, message }"),
        sa.Column("current_step", sa.String(length=50), nullable=True, comment="进行中 step_id"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("idx_tasks_status_created", "tasks", ["status", sa.text("created_at DESC")], unique=False)

    op.create_table(
        "executions",
        sa.Column("execution_id", sa.String(length=50), nullable=False),
        sa.Column("task_id", sa.String(length=50), nullable=False),
        sa.Column("step_id", sa.String(length=50), nullable=True, comment="对应 PlanStep.step_id"),
        sa.Column(
            "phase", sa.String(length=20), nullable=False, comment="REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT"
        ),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("skill_id", sa.String(length=100), nullable=True),
        sa.Column("skill_version", sa.String(length=20), nullable=True),
        sa.Column("input_params", sa.JSON(), nullable=True),
        sa.Column("output_result", sa.JSON(), nullable=True),
        sa.Column(
            "execution_status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
            comment="COMPLETED/FAILED/SKIPPED（新建行默认 PENDING = 待执行）",
        ),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index("idx_executions_task_created", "executions", ["task_id", sa.text("created_at ASC")], unique=False)
    op.create_index("idx_executions_step_id", "executions", ["step_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_executions_step_id", table_name="executions")
    op.drop_index("idx_executions_task_created", table_name="executions")
    op.drop_table("executions")
    op.drop_index("idx_tasks_status_created", table_name="tasks")
    op.drop_table("tasks")
