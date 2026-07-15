from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Resume
from app.schemas import (
    ResumeDedupActionRequest,
    ResumeListResponse,
    ResumeResponse,
    ResumeUpdateRequest,
    ResumeUploadResponse,
)
from app.services.resume import ResumeService

router = APIRouter(prefix="/resumes", tags=["简历管理"])

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "docx"}


@router.post("/upload", response_model=ResumeUploadResponse, summary="上传简历文件")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auto_parse: bool = Query(True, description="上传后是否自动开始后台解析（默认true）"),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小不能超过{MAX_FILE_SIZE // 1024 // 1024}MB")

    import io
    file_obj = io.BytesIO(content)
    file_obj.seek(0)

    service = ResumeService(db)
    try:
        resume, warning = await service.upload_resume(
            file=file_obj,
            filename=file.filename,
            auto_parse=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    if auto_parse:
        background_tasks.add_task(ResumeService.parse_resume_background, resume.resume_id)

    return ResumeUploadResponse(
        resume_id=resume.resume_id,
        file_name=resume.file_name,
        file_size=resume.file_size,
        file_type=resume.file_type,
        parse_status="PARSING" if auto_parse else resume.parse_status,
        created_at=resume.created_at,
    )


@router.post("/{resume_id}/parse", response_model=ResumeResponse, summary="开始后台解析简历")
async def parse_resume(
    resume_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    resume = await service.get_resume(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    resume.parse_status = "PARSING"
    resume.parse_error = None
    await db.commit()
    await db.refresh(resume)

    background_tasks.add_task(ResumeService.parse_resume_background, resume_id)

    return ResumeResponse.model_validate(resume)


@router.get("/{resume_id}/preview", summary="预览原始简历文件")
async def preview_resume(resume_id: str, db: AsyncSession = Depends(get_db)):
    service = ResumeService(db)
    file_stream, filename, content_type = await service.get_file_stream(resume_id)
    if not file_stream:
        raise HTTPException(status_code=404, detail="文件不存在或无法读取")

    from urllib.parse import quote
    encoded_filename = quote(filename)

    return StreamingResponse(
        file_stream,
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/tags/meta", summary="获取所有已用标签与来源（用于筛选下拉）")
async def get_tags_meta(db: AsyncSession = Depends(get_db)):
    """聚合所有简历的 tags 和 source，供前端筛选下拉使用。"""
    result = await db.execute(select(Resume.tags, Resume.source))
    rows = result.all()
    tag_set: set[str] = set()
    source_set: set[str] = set()
    for tags, source in rows:
        if tags:
            for t in tags:
                if t:
                    tag_set.add(t)
        if source:
            source_set.add(source)
    return {"tags": sorted(tag_set), "sources": sorted(source_set)}


@router.get("", response_model=ResumeListResponse, summary="查询简历列表")
async def list_resumes(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    parse_status: str | None = Query(None, description="解析状态筛选"),
    candidate_status: str | None = Query(None, description="候选人状态筛选"),
    keyword: str | None = Query(None, description="关键词搜索（姓名、文件名、手机、邮箱）"),
    tag: str | None = Query(None, description="标签筛选（精确匹配单个标签）"),
    source: str | None = Query(None, description="来源渠道筛选"),
    dedup_status: str | None = Query(None, description="去重状态筛选：NONE/SUSPECTED/CONFIRMED_DUP/IGNORED"),
    date_from: str | None = Query(None, description="上传起始时间 ISO 格式，如 2026-07-01"),
    date_to: str | None = Query(None, description="上传结束时间 ISO 格式，如 2026-07-31"),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    items, total = await service.list_resumes(
        page=page, page_size=page_size, parse_status=parse_status, keyword=keyword,
        candidate_status=candidate_status, tag=tag, source=source,
        dedup_status=dedup_status, date_from=date_from, date_to=date_to,
    )
    return ResumeListResponse(
        items=[ResumeResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{resume_id}", response_model=ResumeResponse, summary="查询简历详情")
async def get_resume(resume_id: str, db: AsyncSession = Depends(get_db)):
    service = ResumeService(db)
    resume = await service.get_resume(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeResponse.model_validate(resume)


@router.put("/{resume_id}", response_model=ResumeResponse, summary="更新简历信息（含标签/来源）")
async def update_resume(
    resume_id: str,
    data: ResumeUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    resume = await service.update_resume(resume_id, data)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeResponse.model_validate(resume)


@router.post("/{resume_id}/dedup", response_model=ResumeResponse, summary="处理疑似重复（确认/忽略/重新检测）")
async def handle_dedup(
    resume_id: str,
    data: ResumeDedupActionRequest,
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    try:
        resume = await service.handle_dedup_action(resume_id, data.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeResponse.model_validate(resume)


@router.delete("/{resume_id}", summary="删除简历")
async def delete_resume(resume_id: str, db: AsyncSession = Depends(get_db)):
    service = ResumeService(db)
    deleted = await service.delete_resume(resume_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="简历不存在")
    return {"message": "简历删除成功"}
