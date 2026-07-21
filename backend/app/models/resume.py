import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def generate_resume_id() -> str:
    return f"res_{uuid.uuid4().hex[:12]}"


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    resume_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_resume_id)
    candidate_name: Mapped[str | None] = mapped_column(String(100), comment="候选人姓名")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="MinIO对象存储路径")
    file_size: Mapped[int | None] = mapped_column(Integer, comment="文件大小（字节）")
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="文件类型：pdf/docx")
    file_hash: Mapped[str | None] = mapped_column(String(64), comment="文件MD5哈希（文件级去重）")
    phone: Mapped[str | None] = mapped_column(String(30), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    parsed_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="解析后结构化内容")
    raw_text: Mapped[str | None] = mapped_column(Text, comment="提取的原始文本")
    parse_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", comment="解析状态：PENDING/PARSING/PARSED/FAILED"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, comment="解析失败错误信息")
    parsing_skill_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("skills.skill_id"), nullable=True)
    parsing_skill_version: Mapped[str | None] = mapped_column(String(20), comment="使用的解析Skill版本")
    parse_time_ms: Mapped[int | None] = mapped_column(Integer, comment="解析耗时ms")
    candidate_status: Mapped[str] = mapped_column(
        String(30),
        default="NEW",
        nullable=False,
        server_default="NEW",
        comment="候选人招聘状态：NEW/SCREENING_PASSED/SCREENING_REJECTED/INTERVIEWING/OFFERED/ARCHIVED",
    )
    # ---- Stage 3 扩展：候选人标签 + 重复检测 ----
    tags: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="候选人标签列表（自由文本标签，如 高潜/技术/管理）",
    )
    source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="来源渠道：BOSS/拉勾/内推/猎头/邮件 等",
    )
    duplicate_of_resume_id: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("resumes.resume_id", ondelete="SET NULL"),
        nullable=True,
        comment="疑似重复的源简历ID（候选人级去重，硬匹配命中后填入）",
    )
    dedup_status: Mapped[str] = mapped_column(
        String(20),
        default="NONE",
        nullable=False,
        server_default="NONE",
        comment="去重状态：NONE/SUSPECTED/CONFIRMED_DUP/IGNORED",
    )
    created_by: Mapped[str | None] = mapped_column(String(50), comment="上传人ID")
