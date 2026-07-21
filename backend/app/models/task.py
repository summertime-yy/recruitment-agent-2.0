import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text, desc
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def generate_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_task_id)
    user_message: Mapped[str] = mapped_column(Text, nullable=False, comment="用户首条消息")
    task_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="MATCH_SCORE/MERGE_CANDIDATES/PROFILE_CANDIDATE/GENERATE_JD/GENERAL_QA/UNKNOWN",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        server_default="PENDING",
        nullable=False,
        comment="状态机（Q2，含 CANCELLED）",
    )
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="Plan 对象（§3.4）")
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="{ jd_id?, candidate_ids? }")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="最终/部分产物 artifacts")
    error: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="{ code, message }（单 JSON，前端一体化消费）"
    )
    current_step: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="进行中 step_id（前端「进行中」展示）"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="进入 EXECUTING 时刻（Q8 超时判定）"
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="进入终态时刻（Q8 超时判定）")

    __table_args__ = (Index("idx_tasks_status_created", "status", desc("created_at")),)

    def __init__(self, **kwargs):
        # 构造即生成业务主键前缀（对齐 Task().task_id.startswith("task_") 契约）
        if "task_id" not in kwargs:
            kwargs["task_id"] = generate_task_id()
        super().__init__(**kwargs)
