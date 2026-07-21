"""候选人状态流转相关 Schema（Stage 3）。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.candidate import STATUS_META, CandidateStatus


class CandidateStatusUpdateRequest(BaseModel):
    to_status: str = Field(
        ..., description="目标状态：NEW/SCREENING_PASSED/SCREENING_REJECTED/INTERVIEWING/OFFERED/ARCHIVED"
    )
    reason: str | None = Field(None, max_length=500, description="变更原因/备注")
    operator: str | None = Field(None, max_length=50, description="操作人ID")


class CandidateStatusInfo(BaseModel):
    """单个状态的可选目标与显示元数据。"""

    value: str
    label: str
    color: str
    is_terminal: bool


class CandidateStatusMetaResponse(BaseModel):
    """状态机元数据：所有状态 + 每个状态允许流转的目标集合。供前端渲染下拉与校验。"""

    current: str
    available_transitions: list[str] = Field(..., description="当前状态允许切换到的目标状态（含自身）")
    all_statuses: list[CandidateStatusInfo]
    transitions_map: dict[str, list[str]] = Field(..., description="全状态转移图：from -> [to...]")


class CandidateStatusHistoryItem(BaseModel):
    history_id: str
    resume_id: str
    from_status: str | None = None
    to_status: str
    reason: str | None = None
    operator: str | None = None
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateStatusHistoryResponse(BaseModel):
    items: list[CandidateStatusHistoryItem]
    total: int


# 供 schemas/__init__ 复用的构造函数 ------------------------------------------------
def build_status_meta(current_status: str) -> CandidateStatusMetaResponse:
    from app.models.candidate import ALLOWED_TRANSITIONS

    all_statuses = [
        CandidateStatusInfo(
            value=s,
            label=STATUS_META[s]["label"],
            color=STATUS_META[s]["color"],
            is_terminal=s in CandidateStatus.TERMINAL,
        )
        for s in CandidateStatus.ALL
    ]
    transitions_map = {frm: sorted(tos) for frm, tos in ALLOWED_TRANSITIONS.items()}
    available = sorted(ALLOWED_TRANSITIONS.get(current_status, set()))
    return CandidateStatusMetaResponse(
        current=current_status,
        available_transitions=available,
        all_statuses=all_statuses,
        transitions_map=transitions_map,
    )


# ---------------------------------------------------------------------------
# 候选人备注/评价（Stage 3）
# ---------------------------------------------------------------------------


class CandidateNoteCreateRequest(BaseModel):
    """新建备注/评价。"""

    note_type: str = Field("NOTE", description="NOTE=备注，EVALUATION=评价")
    content: str = Field(..., min_length=1, max_length=2000, description="内容")
    rating: int | None = Field(None, ge=1, le=5, description="评分1-5（仅EVALUATION使用）")
    author: str | None = Field(None, max_length=50, description="作者ID")


class CandidateNoteUpdateRequest(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=2000)
    rating: int | None = Field(None, ge=1, le=5)


class CandidateNoteItem(BaseModel):
    note_id: str
    resume_id: str
    note_type: str
    content: str
    rating: int | None = None
    author: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateNoteListResponse(BaseModel):
    items: list[CandidateNoteItem]
    total: int
