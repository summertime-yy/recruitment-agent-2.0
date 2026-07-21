"""候选人状态流转 + 备注评价 API（Stage 3）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    CandidateNoteCreateRequest,
    CandidateNoteItem,
    CandidateNoteListResponse,
    CandidateNoteUpdateRequest,
    CandidateStatusHistoryResponse,
    CandidateStatusMetaResponse,
    CandidateStatusUpdateRequest,
    ResumeResponse,
)
from app.services.candidate import CandidateService

router = APIRouter(prefix="/candidates", tags=["候选人管理"])


# ---------------------------------------------------------------------------
# 状态流转
# ---------------------------------------------------------------------------


@router.get(
    "/{resume_id}/status/meta",
    response_model=CandidateStatusMetaResponse,
    summary="获取候选人状态机元数据（当前状态+可流转目标）",
)
async def get_status_meta(resume_id: str, db: AsyncSession = Depends(get_db)):
    service = CandidateService(db)
    meta = await service.get_status_meta(resume_id)
    if not meta:
        raise HTTPException(status_code=404, detail="简历不存在")
    return meta


@router.put(
    "/{resume_id}/status",
    response_model=ResumeResponse,
    summary="更新候选人状态（带状态机校验与历史记录）",
)
async def update_candidate_status(
    resume_id: str,
    data: CandidateStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = CandidateService(db)
    resume, error = await service.update_status(resume_id, data)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    if error:
        raise HTTPException(status_code=400, detail=error)
    return ResumeResponse.model_validate(resume)


@router.get(
    "/{resume_id}/status/history",
    response_model=CandidateStatusHistoryResponse,
    summary="查询候选人状态流转历史",
)
async def get_status_history(resume_id: str, db: AsyncSession = Depends(get_db)):
    service = CandidateService(db)
    return await service.list_history(resume_id)


# ---------------------------------------------------------------------------
# 备注与评价
# ---------------------------------------------------------------------------


@router.get(
    "/{resume_id}/notes",
    response_model=CandidateNoteListResponse,
    summary="查询候选人备注/评价列表",
)
async def list_notes(resume_id: str, db: AsyncSession = Depends(get_db)):
    service = CandidateService(db)
    return await service.list_notes(resume_id)


@router.post(
    "/{resume_id}/notes",
    response_model=CandidateNoteItem,
    status_code=201,
    summary="新增备注/评价",
)
async def create_note(
    resume_id: str,
    data: CandidateNoteCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = CandidateService(db)
    item = await service.create_note(resume_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="简历不存在")
    return item


@router.put(
    "/{resume_id}/notes/{note_id}",
    response_model=CandidateNoteItem,
    summary="更新备注/评价",
)
async def update_note(
    resume_id: str,
    note_id: str,
    data: CandidateNoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = CandidateService(db)
    item = await service.update_note(resume_id, note_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="备注不存在")
    return item


@router.delete(
    "/{resume_id}/notes/{note_id}",
    summary="删除备注/评价",
)
async def delete_note(
    resume_id: str,
    note_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = CandidateService(db)
    deleted = await service.delete_note(resume_id, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="备注不存在")
    return {"message": "删除成功"}
