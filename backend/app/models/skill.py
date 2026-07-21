from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    skill_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    author: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    trigger_conditions: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class SkillVersion(Base):
    __tablename__ = "skill_versions"

    version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(String(100), ForeignKey("skills.skill_id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content_path: Mapped[str] = mapped_column(String(500), nullable=False)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tool_chain: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    error_handling: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    changelog: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    traffic_weight: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float | None] = mapped_column(Float)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("skill_id", "version", name="uq_skill_version"),)


class SkillExecutionLog(Base):
    __tablename__ = "skill_execution_logs"

    execution_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(String(100), ForeignKey("skills.skill_id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(50))
    user_id: Mapped[str | None] = mapped_column(String(50))
    input_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    execution_status: Mapped[str] = mapped_column(String(20))
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    validation_score: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
