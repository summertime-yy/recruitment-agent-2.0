from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    JDGenerateRequest,
    JDGenerateResponse,
    JDListResponse,
    JDResponse,
    JDUpdateRequest,
)
from app.services.jd import JDService

router = APIRouter(prefix="/jds", tags=["JD管理"])


@router.post("/generate", response_model=JDGenerateResponse, summary="AI生成JD")
async def generate_jd(
    request: JDGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = JDService(db)
    try:
        jd, exec_log = await service.generate_jd(request)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JDGenerateResponse(
        jd=JDResponse.model_validate(jd),
        skill_execution_id=exec_log.execution_id,
        execution_time_ms=exec_log.execution_time_ms or 0,
        validation_score=exec_log.validation_score or 0.0,
    )


@router.get("", response_model=JDListResponse, summary="查询JD列表")
async def list_jds(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="JD状态筛选：DRAFT/PUBLISHED/ARCHIVED"),
    keyword: str | None = Query(None, description="关键词搜索（职位名称）"),
    db: AsyncSession = Depends(get_db),
):
    service = JDService(db)
    items, total = await service.list_jds(page=page, page_size=page_size, status=status, keyword=keyword)
    return JDListResponse(
        items=[JDResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{jd_id}", response_model=JDResponse, summary="查询JD详情")
async def get_jd(jd_id: str, db: AsyncSession = Depends(get_db)):
    service = JDService(db)
    jd = await service.get_jd(jd_id)
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return JDResponse.model_validate(jd)


@router.put("/{jd_id}", response_model=JDResponse, summary="更新JD")
async def update_jd(
    jd_id: str,
    request: JDUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = JDService(db)
    jd = await service.update_jd(jd_id, request)
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return JDResponse.model_validate(jd)


@router.delete("/{jd_id}", summary="删除JD")
async def delete_jd(jd_id: str, db: AsyncSession = Depends(get_db)):
    service = JDService(db)
    deleted = await service.delete_jd(jd_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="JD not found")
    return {"message": "JD deleted successfully"}
