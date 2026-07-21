"""候选人状态流转（Stage 3）。

candidate_status 与 parse_status 正交：
- parse_status 管"简历文件解析"流程（PENDING/PARSING/PARSED/FAILED）
- candidate_status 管"招聘流程"流转（NEW -> 初筛 -> 面试 -> 录用/淘汰）
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


# ---------------------------------------------------------------------------
# 候选人状态枚举
# ---------------------------------------------------------------------------
class CandidateStatus:
    """候选人招聘状态。使用字符串常量而非 Enum，便于 Alembic/扩展，前端可直接对齐。"""

    NEW = "NEW"  # 新简历（默认）
    SCREENING_PASSED = "SCREENING_PASSED"  # 初筛通过
    SCREENING_REJECTED = "SCREENING_REJECTED"  # 初筛淘汰
    INTERVIEWING = "INTERVIEWING"  # 面试中
    OFFERED = "OFFERED"  # 录用
    ARCHIVED = "ARCHIVED"  # 已归档（不合适/冻结）

    ALL: tuple[str, ...] = (
        NEW,
        SCREENING_PASSED,
        SCREENING_REJECTED,
        INTERVIEWING,
        OFFERED,
        ARCHIVED,
    )

    # 终态：到达后一般不再流转（除非重新激活）
    TERMINAL: tuple[str, ...] = (OFFERED, ARCHIVED)


# ---------------------------------------------------------------------------
# 合法状态转移图：from_status -> {允许的 to_status}
# 未列出的 from_status 表示不允许再流转（终态）。允许回到自身（幂等切换）。
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    CandidateStatus.NEW: {
        CandidateStatus.NEW,
        CandidateStatus.SCREENING_PASSED,
        CandidateStatus.SCREENING_REJECTED,
        CandidateStatus.ARCHIVED,
    },
    CandidateStatus.SCREENING_PASSED: {
        CandidateStatus.SCREENING_PASSED,
        CandidateStatus.INTERVIEWING,
        CandidateStatus.SCREENING_REJECTED,
        CandidateStatus.ARCHIVED,
    },
    CandidateStatus.INTERVIEWING: {
        CandidateStatus.INTERVIEWING,
        CandidateStatus.OFFERED,
        CandidateStatus.SCREENING_REJECTED,
        CandidateStatus.ARCHIVED,
    },
    CandidateStatus.SCREENING_REJECTED: {
        CandidateStatus.SCREENING_REJECTED,
        CandidateStatus.ARCHIVED,
        CandidateStatus.NEW,  # 允许重新激活回到候选池
    },
    CandidateStatus.OFFERED: {CandidateStatus.OFFERED, CandidateStatus.ARCHIVED},
    CandidateStatus.ARCHIVED: {CandidateStatus.ARCHIVED, CandidateStatus.NEW},
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """判断 from->to 是否合法。未登记的 from（理论上不会出现）默认不允许。"""
    allowed = ALLOWED_TRANSITIONS.get(from_status)
    return bool(allowed and to_status in allowed)


# ---------------------------------------------------------------------------
# 状态显示信息（label + 颜色），供后端统一返回，前端可复用
# ---------------------------------------------------------------------------
STATUS_META: dict[str, dict[str, str]] = {
    CandidateStatus.NEW: {"label": "新简历", "color": "default"},
    CandidateStatus.SCREENING_PASSED: {"label": "初筛通过", "color": "blue"},
    CandidateStatus.INTERVIEWING: {"label": "面试中", "color": "processing"},
    CandidateStatus.OFFERED: {"label": "已录用", "color": "success"},
    CandidateStatus.SCREENING_REJECTED: {"label": "初筛淘汰", "color": "warning"},
    CandidateStatus.ARCHIVED: {"label": "已归档", "color": "default"},
}


def generate_history_id() -> str:
    return f"csh_{uuid.uuid4().hex[:12]}"


class CandidateStatusHistory(Base, TimestampMixin):
    """候选人状态流转历史。每次状态变更追加一条记录，支持审计与时间线展示。"""

    __tablename__ = "candidate_status_history"

    history_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_history_id)
    resume_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(30), comment="变更前状态；首条为 NULL")
    to_status: Mapped[str] = mapped_column(String(30), nullable=False, comment="变更后状态")
    reason: Mapped[str | None] = mapped_column(String(500), comment="变更原因/备注")
    operator: Mapped[str | None] = mapped_column(String(50), comment="操作人ID")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)


# ---------------------------------------------------------------------------
# 候选人备注与评价（Stage 3）
# ---------------------------------------------------------------------------


class CandidateNoteType:
    """备注类型。NOTE=普通备注，EVALUATION=带评分的评价。"""

    NOTE = "NOTE"
    EVALUATION = "EVALUATION"
    ALL: tuple[str, ...] = (NOTE, EVALUATION)


NOTE_TYPE_META: dict[str, dict[str, str]] = {
    CandidateNoteType.NOTE: {"label": "备注", "color": "default"},
    CandidateNoteType.EVALUATION: {"label": "评价", "color": "gold"},
}


def generate_note_id() -> str:
    return f"cnt_{uuid.uuid4().hex[:12]}"


class CandidateNote(Base, TimestampMixin):
    """候选人备注/评价记录。

    一条记录可以是纯文字备注（NOTE），也可以是带评分的评价（EVALUATION）。
    通过 resume_id 关联候选人（本系统候选人=已解析的简历）。
    """

    __tablename__ = "candidate_notes"

    note_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_note_id)
    resume_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_type: Mapped[str] = mapped_column(
        String(20),
        default=CandidateNoteType.NOTE,
        nullable=False,
        server_default="NOTE",
        comment="类型：NOTE=备注，EVALUATION=评价",
    )
    content: Mapped[str] = mapped_column(String(2000), nullable=False, comment="备注/评价内容")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="评分1-5（仅EVALUATION类型使用）")
    author: Mapped[str | None] = mapped_column(String(50), comment="作者/操作人ID")
