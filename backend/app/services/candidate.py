"""候选人状态流转 + 备注评价服务（Stage 3）。"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import (
    ALLOWED_TRANSITIONS,
    CandidateNote,
    CandidateNoteType,
    CandidateStatus,
    CandidateStatusHistory,
    is_valid_transition,
)
from app.models.resume import Resume
from app.schemas.candidate import (
    CandidateNoteCreateRequest,
    CandidateNoteItem,
    CandidateNoteListResponse,
    CandidateNoteUpdateRequest,
    CandidateStatusHistoryItem,
    CandidateStatusHistoryResponse,
    CandidateStatusMetaResponse,
    CandidateStatusUpdateRequest,
    build_status_meta,
)

logger = logging.getLogger(__name__)


class CandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_status_meta(self, resume_id: str) -> CandidateStatusMetaResponse | None:
        """返回指定简历当前状态的可流转目标与全局状态机元数据。"""
        resume = await self._get_resume(resume_id)
        if not resume:
            return None
        return build_status_meta(resume.candidate_status)

    async def update_status(
        self,
        resume_id: str,
        req: CandidateStatusUpdateRequest,
    ) -> tuple[Resume | None, str | None]:
        """更新候选人状态。返回 (resume, error)。error 非 None 表示业务校验失败。"""
        resume = await self._get_resume(resume_id)
        if not resume:
            return None, "简历不存在"

        to_status = req.to_status.strip().upper()
        if to_status not in CandidateStatus.ALL:
            return resume, f"非法状态值: {req.to_status}，合法值: {', '.join(CandidateStatus.ALL)}"

        from_status = resume.candidate_status
        if from_status == to_status:
            return resume, None

        if not is_valid_transition(from_status, to_status):
            allowed = sorted(ALLOWED_TRANSITIONS.get(from_status, set()))
            return resume, (
                f"不允许的状态流转: {from_status} -> {to_status}。"
                f"当前状态 {from_status} 仅可切换为: {', '.join(allowed) if allowed else '（终态，不可流转）'}"
            )

        history = CandidateStatusHistory(
            resume_id=resume.resume_id,
            from_status=from_status,
            to_status=to_status,
            reason=req.reason,
            operator=req.operator,
            occurred_at=datetime.utcnow(),
        )
        self.db.add(history)

        resume.candidate_status = to_status
        resume.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(resume)
        logger.info(
            "Candidate status changed: resume=%s %s -> %s by=%s reason=%s",
            resume.resume_id, from_status, to_status, req.operator, req.reason,
        )
        return resume, None

    async def list_history(self, resume_id: str) -> CandidateStatusHistoryResponse:
        """按时间倒序返回该简历的状态流转历史。"""
        resume = await self._get_resume(resume_id)
        if not resume:
            return CandidateStatusHistoryResponse(items=[], total=0)
        result = await self.db.execute(
            select(CandidateStatusHistory)
            .where(CandidateStatusHistory.resume_id == resume_id)
            .order_by(desc(CandidateStatusHistory.occurred_at))
        )
        items = result.scalars().all()
        return CandidateStatusHistoryResponse(
            items=[CandidateStatusHistoryItem.model_validate(it) for it in items],
            total=len(items),
        )

    # -----------------------------------------------------------------------
    # 备注与评价（Stage 3）
    # -----------------------------------------------------------------------

    async def list_notes(self, resume_id: str) -> CandidateNoteListResponse:
        """按时间倒序返回候选人的备注/评价列表。"""
        result = await self.db.execute(
            select(CandidateNote)
            .where(CandidateNote.resume_id == resume_id)
            .order_by(desc(CandidateNote.created_at))
        )
        items = result.scalars().all()
        return CandidateNoteListResponse(
            items=[CandidateNoteItem.model_validate(it) for it in items],
            total=len(items),
        )

    async def create_note(
        self, resume_id: str, req: CandidateNoteCreateRequest
    ) -> CandidateNoteItem | None:
        """新建备注/评价。"""
        resume = await self._get_resume(resume_id)
        if not resume:
            return None
        note_type = req.note_type.strip().upper()
        if note_type not in CandidateNoteType.ALL:
            note_type = CandidateNoteType.NOTE
        if note_type == CandidateNoteType.EVALUATION and req.rating is None:
            # 评价类型未给评分时默认 3 分
            rating = 3
        else:
            rating = req.rating
        note = CandidateNote(
            resume_id=resume_id,
            note_type=note_type,
            content=req.content,
            rating=rating,
            author=req.author,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        return CandidateNoteItem.model_validate(note)

    async def update_note(
        self, resume_id: str, note_id: str, req: CandidateNoteUpdateRequest
    ) -> CandidateNoteItem | None:
        """更新备注/评价内容或评分。"""
        result = await self.db.execute(
            select(CandidateNote).where(
                CandidateNote.note_id == note_id,
                CandidateNote.resume_id == resume_id,
            )
        )
        note = result.scalar_one_or_none()
        if not note:
            return None
        if req.content is not None:
            note.content = req.content
        if req.rating is not None:
            note.rating = req.rating
        note.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(note)
        return CandidateNoteItem.model_validate(note)

    async def delete_note(self, resume_id: str, note_id: str) -> bool:
        """删除备注/评价。"""
        result = await self.db.execute(
            select(CandidateNote).where(
                CandidateNote.note_id == note_id,
                CandidateNote.resume_id == resume_id,
            )
        )
        note = result.scalar_one_or_none()
        if not note:
            return False
        await self.db.delete(note)
        await self.db.commit()
        return True

    async def _get_resume(self, resume_id: str) -> Resume | None:
        result = await self.db.execute(
            select(Resume).where(Resume.resume_id == resume_id)
        )
        return result.scalar_one_or_none()
