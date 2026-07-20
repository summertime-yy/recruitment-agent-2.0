import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def generate_execution_id() -> str:
    return f"exec_{uuid.uuid4().hex[:12]}"


class Execution(Base, TimestampMixin):
    __tablename__ = "executions"

    execution_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=generate_execution_id
    )
    task_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False,
        comment="归属任务（删除 Task 级联清理）",
    )
    step_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="对应 PlanStep.step_id"
    )
    phase: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT",
    )
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="调用的工具/Skill 名")
    skill_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="命中 Skill 时填")
    skill_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="入参快照")
    output_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="出参快照")
    execution_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", server_default="PENDING", nullable=False,
        comment="COMPLETED/FAILED/SKIPPED（新建行默认 PENDING = 待执行，计划域未列但属必要前置态）",
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_executions_task_created", "task_id", "created_at"),
        Index("idx_executions_step_id", "step_id"),
    )

    def __init__(self, **kwargs):
        # 构造即生成业务主键前缀（对齐 Execution().execution_id.startswith("exec_") 契约）
        if "execution_id" not in kwargs:
            kwargs["execution_id"] = generate_execution_id()
        super().__init__(**kwargs)
