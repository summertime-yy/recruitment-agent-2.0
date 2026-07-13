import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def generate_resume_id() -> str:
    return f"res_{uuid.uuid4().hex[:12]}"


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    resume_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=generate_resume_id
    )
    candidate_name: Mapped[str | None] = mapped_column(String(100), comment="候选人姓名")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="MinIO对象存储路径")
    file_size: Mapped[int | None] = mapped_column(Integer, comment="文件大小（字节）")
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="文件类型：pdf/docx")
    file_hash: Mapped[str | None] = mapped_column(String(64), comment="文件MD5哈希（去重用）")
    phone: Mapped[str | None] = mapped_column(String(30), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    parsed_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="解析后结构化内容")
    raw_text: Mapped[str | None] = mapped_column(Text, comment="提取的原始文本")
    parse_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", comment="解析状态：PENDING/PARSING/PARSED/FAILED"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, comment="解析失败错误信息")
    parsing_skill_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("skills.skill_id"), nullable=True
    )
    parsing_skill_version: Mapped[str | None] = mapped_column(String(20), comment="使用的解析Skill版本")
    parse_time_ms: Mapped[int | None] = mapped_column(Integer, comment="解析耗时ms")
    created_by: Mapped[str | None] = mapped_column(String(50), comment="上传人ID")
