from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    BatchMatchRequest,
    BatchTaskResponse,
    BatchTaskStatusResponse,
    MatchScoreRequest,
    MatchScoreResponse,
)
from app.services.match import (
    MatchNotFoundError,
    MatchService,
    MatchSkillError,
    ResumeNotParsedError,
)

router = APIRouter(prefix="/match-scores", tags=["人岗匹配"])


@router.post("", response_model=MatchScoreResponse, status_code=201, summary="单点触发人岗匹配")
async def create_match_score(request: MatchScoreRequest, db: AsyncSession = Depends(get_db)):
    service = MatchService(db)
    try:
        score = await service.match_one(request.jd_id, request.resume_id, force=request.force)
    except ResumeNotParsedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MatchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MatchSkillError as e:
        raise HTTPException(status_code=500, detail=str(e))
    resp = MatchScoreResponse.model_validate(score)
    resp.is_stale = await service.compute_is_stale(score)
    return resp


@router.post("/batch", response_model=BatchTaskResponse, status_code=202, summary="批量触发人岗匹配")
async def create_batch_match(request: BatchMatchRequest, db: AsyncSession = Depends(get_db)):
    service = MatchService(db)
    try:
        handle = await service.batch_match(
            request.jd_id,
            resume_ids=request.resume_ids,
            limit=request.limit,
            force=request.force,
        )
    except MatchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return BatchTaskResponse(
        task_id=handle.task_id,
        jd_id=handle.jd_id,
        total_submitted=handle.total_submitted,
        submitted_at=handle.submitted_at,
    )


@router.get("/batch/{task_id}", response_model=BatchTaskStatusResponse, summary="查询批量匹配任务状态")
async def get_batch_status(task_id: str, db: AsyncSession = Depends(get_db)):
    service = MatchService(db)
    state = service.get_batch_status(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="batch task not found")
    return BatchTaskStatusResponse(
        task_id=state["task_id"],
        jd_id=state["jd_id"],
        total=state["total"],
        completed=state["completed"],
        failed=state["failed"],
        status=state["status"],
        started_at=state["started_at"],
        finished_at=state["finished_at"],
    )


@router.get("/{score_id}", response_model=MatchScoreResponse, summary="查询单条匹配详情")
async def get_match_score(score_id: str, db: AsyncSession = Depends(get_db)):
    service = MatchService(db)
    score = await service.get_score(score_id)
    if score is None:
        raise HTTPException(status_code=404, detail="match score not found")
    resp = MatchScoreResponse.model_validate(score)
    resp.is_stale = await service.compute_is_stale(score)
    return resp
