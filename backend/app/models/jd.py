import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def generate_uuid() -> str:
    return str(uuid.uuid4())


class JDTemplate(Base, TimestampMixin):
    __tablename__ = "jd_templates"

    template_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=generate_uuid
    )
    template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_type: Mapped[str] = mapped_column(String(30))
    template_content: Mapped[dict[str, Any]] = mapped_column(JSON)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)


class JD(Base, TimestampMixin):
    __tablename__ = "jds"

    jd_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=generate_uuid
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str | None] = mapped_column(String(50))
    level: Mapped[str | None] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(100))
    job_type: Mapped[str | None] = mapped_column(String(30), comment="工作类型：全职/兼职/实习")
    recruit_type: Mapped[str | None] = mapped_column(String(30), comment="招聘类型：社招/校招/内推")
    headcount: Mapped[int | None] = mapped_column(Integer, default=1, comment="招聘人数")
    experience_years: Mapped[str | None] = mapped_column(String(30), comment="经验年限要求，如3-5年")
    education_requirement: Mapped[str | None] = mapped_column(String(30), comment="学历要求，如本科及以上")
    salary_range: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list[str] | None] = mapped_column(JSON)
    requirements: Mapped[list[str] | None] = mapped_column(JSON)
    required_skills: Mapped[list[str] | None] = mapped_column(JSON)
    preferred_skills: Mapped[list[str] | None] = mapped_column(JSON)
    compliance_check: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    template_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("jd_templates.template_id"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
