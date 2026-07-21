import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def generate_match_score_id() -> str:
    return f"ms_{uuid.uuid4().hex[:12]}"


class MatchScore(Base, TimestampMixin):
    __tablename__ = "match_scores"

    score_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_match_score_id)
    jd_id: Mapped[str] = mapped_column(String(50), ForeignKey("jds.jd_id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, comment="综合匹配度0-100")
    dimension_scores: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="维度分：skill/experience/education + overall_reasoning"
    )
    matching_skill_id: Mapped[str | None] = mapped_column(String(100), comment="匹配Skill ID")
    matching_skill_version: Mapped[str | None] = mapped_column(String(20), comment="匹配Skill版本")
    skill_execution_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("skill_execution_logs.execution_id"), nullable=True
    )
    resume_updated_at_snapshot: Mapped[datetime | None] = mapped_column(
        DateTime, comment="生成时简历updated_at快照，用于陈旧判断"
    )
    jd_updated_at_snapshot: Mapped[datetime | None] = mapped_column(DateTime, comment="生成时JD updated_at快照")
    status: Mapped[str] = mapped_column(
        String(20),
        default="COMPLETED",
        server_default="COMPLETED",
        nullable=False,
        comment="COMPLETED/FAILED/STALE",
    )
    error_message: Mapped[str | None] = mapped_column(Text, comment="Skill失败原因")

    __table_args__ = (
        UniqueConstraint("jd_id", "resume_id", name="uq_match_scores_jd_resume"),
        Index("idx_match_scores_jd_id_overall", "jd_id", desc("overall_score")),
        Index("idx_match_scores_resume_id", "resume_id"),
    )
