import hashlib
import logging
import uuid
from datetime import datetime
from io import BytesIO
from typing import BinaryIO

from minio import Minio
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skill_registry import get_skill_registry
from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.minio import get_minio
from app.models import Resume, SkillExecutionLog
from app.schemas.resume import ResumeUpdateRequest
from app.utils.document_parser import extract_text

logger = logging.getLogger(__name__)
settings = get_settings()


class ResumeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.minio: Minio = get_minio()

    # -----------------------------------------------------------------------
    # Stage 3：候选人级去重（硬匹配手机号/邮箱）
    # -----------------------------------------------------------------------
    async def _detect_duplicate(self, resume: Resume) -> None:
        """解析成功后检测是否存在疑似重复的候选人。

        硬匹配规则（命中任一即标记 SUSPECTED）：
        - phone 非空 且 与其他 resume 的 phone 完全相等
        - email 非空 且 与其他 resume 的 email（小写）相等
        只标记不拦截，由人工决定合并/忽略。
        """
        if not resume.phone and not resume.email:
            return
        conditions = []
        if resume.phone:
            conditions.append(Resume.phone == resume.phone)
        if resume.email:
            conditions.append(Resume.email == resume.email.lower())
        from sqlalchemy import or_
        result = await self.db.execute(
            select(Resume.resume_id).where(
                Resume.resume_id != resume.resume_id,
                Resume.parse_status == "PARSED",
                or_(*conditions),
            ).order_by(Resume.created_at.asc()).limit(1)
        )
        dup_id = result.scalar_one_or_none()
        if dup_id:
            resume.duplicate_of_resume_id = dup_id
            resume.dedup_status = "SUSPECTED"
        else:
            resume.duplicate_of_resume_id = None
            resume.dedup_status = "NONE"

    async def handle_dedup_action(self, resume_id: str, action: str) -> Resume | None:
        """人工处理去重状态。"""
        resume = await self.get_resume(resume_id)
        if not resume:
            return None
        if action == "CONFIRM_DUP":
            resume.dedup_status = "CONFIRMED_DUP"
        elif action == "IGNORE":
            resume.dedup_status = "IGNORED"
        elif action == "RECHECK":
            await self._detect_duplicate(resume)
        else:
            raise ValueError(f"unsupported dedup action: {action}")
        resume.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(resume)
        return resume


    @staticmethod
    def _generate_id() -> str:
        return f"res_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _get_file_ext(filename: str) -> str:
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    def _upload_to_minio(self, file_bytes: bytes, object_name: str) -> None:
        file_ext = object_name.rsplit(".", 1)[-1] if "." in object_name else ""
        self.minio.put_object(
            bucket_name=settings.MINIO_RESUME_BUCKET,
            object_name=object_name,
            data=BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=self._get_content_type(file_ext),
        )

    @staticmethod
    def _get_content_type(file_ext: str) -> str:
        return {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(file_ext, "application/octet-stream")

    @staticmethod
    def _compute_md5(file_bytes: bytes) -> str:
        return hashlib.md5(file_bytes).hexdigest()

    async def upload_resume(
        self,
        file: BinaryIO,
        filename: str,
        created_by: str | None = None,
        auto_parse: bool = True,
    ) -> tuple[Resume, str | None]:
        file_bytes = file.read()
        file_size = len(file_bytes)
        file_ext = self._get_file_ext(filename)
        file_hash = self._compute_md5(file_bytes)

        existing = await self.db.execute(
            select(Resume).where(Resume.file_hash == file_hash)
        )
        existing_resume = existing.scalar_one_or_none()
        if existing_resume:
            logger.info(f"Resume with same hash already exists: {existing_resume.resume_id}")
            return existing_resume, "该简历文件已上传过"

        try:
            raw_text, detected_type = extract_text(BytesIO(file_bytes), filename)
        except ValueError as e:
            raise ValueError(str(e))

        resume_id = self._generate_id()
        object_name = f"{resume_id}.{file_ext}"
        self._upload_to_minio(file_bytes, object_name)

        resume = Resume(
            resume_id=resume_id,
            file_name=filename,
            file_path=object_name,
            file_size=file_size,
            file_type=detected_type,
            file_hash=file_hash,
            raw_text=raw_text,
            parse_status="PENDING",
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(resume)
        await self.db.flush()

        parse_error = None
        if auto_parse:
            try:
                await self._parse_resume_internal(resume, raw_text)
            except Exception as e:
                logger.error(f"Auto-parse failed for {resume.resume_id}: {e}")
                parse_error = str(e)

        await self.db.commit()
        await self.db.refresh(resume)
        return resume, parse_error

    async def _parse_resume_internal(self, resume: Resume, raw_text: str) -> None:
        registry = get_skill_registry()
        skill = registry.get_skill("resume-parsing")
        if not skill:
            raise RuntimeError("resume-parsing skill not found in registry")

        resume.parse_status = "PARSING"
        resume.parse_error = None
        # Stage 3：解析成功后执行候选人级去重检测（硬匹配手机号/邮箱）
        await self._detect_duplicate(resume)
        await self.db.flush()

        start_time = datetime.utcnow()
        skill_input = {
            "raw_text": raw_text[:3000],
            "file_name": resume.file_name,
        }
        result = await skill.execute(skill_input)
        elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        exec_log = SkillExecutionLog(
            skill_id=skill.skill_id,
            version=skill.version,
            task_id=resume.resume_id,
            input_params={"file_name": resume.file_name},
            output_result=result.output if result.success else None,
            execution_status=result.status.value,
            execution_time_ms=elapsed_ms,
            validation_score=result.validation_score,
            error_message=result.error_message,
            executed_at=start_time,
        )
        self.db.add(exec_log)
        await self.db.flush()

        if not result.success or not result.output:
            resume.parse_status = "FAILED"
            resume.parse_error = result.error_message or "解析失败"
            resume.parse_time_ms = elapsed_ms
            return

        output = result.output
        resume.candidate_name = output.get("candidate_name")
        resume.phone = output.get("phone")
        resume.email = output.get("email")
        resume.parsing_skill_id = skill.skill_id
        resume.parsing_skill_version = skill.version
        resume.parse_time_ms = elapsed_ms
        resume.parsed_content = {
            "summary": output.get("summary"),
            "education": output.get("education", []),
            "work_experience": output.get("work_experience", []),
            "project_experience": output.get("project_experience", []),
            "skills": output.get("skills", []),
        }
        resume.parse_status = "PARSED"
        resume.parse_error = None

    async def parse_resume(self, resume_id: str) -> Resume | None:
        resume = await self.get_resume(resume_id)
        if not resume:
            return None
        if not resume.raw_text:
            resume.parse_status = "FAILED"
            resume.parse_error = "没有可用的原始文本，请重新上传"
            await self.db.commit()
            await self.db.refresh(resume)
            return resume

        await self._parse_resume_internal(resume, resume.raw_text)
        await self.db.commit()
        await self.db.refresh(resume)
        return resume

    async def get_resume(self, resume_id: str) -> Resume | None:
        result = await self.db.execute(select(Resume).where(Resume.resume_id == resume_id))
        return result.scalar_one_or_none()

    async def list_resumes(
        self,
        page: int = 1,
        page_size: int = 10,
        parse_status: str | None = None,
        keyword: str | None = None,
        candidate_status: str | None = None,
        tag: str | None = None,
        source: str | None = None,
        dedup_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[list[Resume], int]:
        query = select(Resume)
        count_query = select(Resume)

        if parse_status:
            query = query.where(Resume.parse_status == parse_status)
            count_query = count_query.where(Resume.parse_status == parse_status)

        if candidate_status:
            query = query.where(Resume.candidate_status == candidate_status)
            count_query = count_query.where(Resume.candidate_status == candidate_status)

        if source:
            query = query.where(Resume.source == source)
            count_query = count_query.where(Resume.source == source)

        if dedup_status:
            query = query.where(Resume.dedup_status == dedup_status)
            count_query = count_query.where(Resume.dedup_status == dedup_status)

        if tag:
            # JSONB 数组包含查询：tags @> '["tag"]'
            query = query.where(Resume.tags.contains([tag]))
            count_query = count_query.where(Resume.tags.contains([tag]))

        if date_from:
            try:
                df = datetime.fromisoformat(date_from)
                query = query.where(Resume.created_at >= df)
                count_query = count_query.where(Resume.created_at >= df)
            except ValueError:
                pass

        if date_to:
            try:
                dt = datetime.fromisoformat(date_to)
                query = query.where(Resume.created_at <= dt)
                count_query = count_query.where(Resume.created_at <= dt)
            except ValueError:
                pass

        if keyword:
            kw = f"%{keyword}%"
            kw_cond = (
                (Resume.candidate_name.ilike(kw))
                | (Resume.file_name.ilike(kw))
                | (Resume.phone.ilike(kw))
                | (Resume.email.ilike(kw))
            )
            query = query.where(kw_cond)
            count_query = count_query.where(kw_cond)

        total_result = await self.db.execute(count_query.with_only_columns(Resume.resume_id))
        total = len(total_result.fetchall())

        query = query.order_by(desc(Resume.created_at)).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def delete_resume(self, resume_id: str) -> bool:
        resume = await self.get_resume(resume_id)
        if not resume:
            return False
        try:
            self.minio.remove_object(settings.MINIO_RESUME_BUCKET, resume.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete MinIO object {resume.file_path}: {e}")
        await self.db.delete(resume)
        await self.db.commit()
        return True

    async def get_file_stream(self, resume_id: str):
        import io

        from minio.error import S3Error

        result = await self.db.execute(select(Resume).where(Resume.resume_id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            return None, None, None

        try:
            response = self.minio.get_object(
                settings.MINIO_RESUME_BUCKET,
                resume.file_path,
            )
            data = response.read()
            response.close()
            response.release_conn()
            return io.BytesIO(data), resume.file_name, self._get_content_type(
                self._get_file_ext(resume.file_name)
            )
        except S3Error as e:
            logger.error(f"Failed to get file from MinIO: {e}")
            return None, None, None

    async def update_resume(self, resume_id: str, data: ResumeUpdateRequest) -> Resume | None:
        resume = await self.get_resume(resume_id)
        if not resume:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "candidate_name" in update_data:
            resume.candidate_name = update_data["candidate_name"]
        if "phone" in update_data:
            resume.phone = update_data["phone"]
        if "email" in update_data:
            resume.email = update_data["email"]
        if "parsed_content" in update_data and update_data["parsed_content"] is not None:
            resume.parsed_content = update_data["parsed_content"].model_dump()
        if "tags" in update_data:
            resume.tags = update_data["tags"]
        if "source" in update_data:
            resume.source = update_data["source"]

        resume.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(resume)
        return resume

    @staticmethod
    async def parse_resume_background(resume_id: str) -> None:
        async with async_session_factory() as db:
            try:
                result = await db.execute(select(Resume).where(Resume.resume_id == resume_id))
                resume = result.scalar_one_or_none()
                if not resume:
                    logger.error(f"Background parse: resume {resume_id} not found")
                    return

                if not resume.raw_text:
                    resume.parse_status = "FAILED"
                    resume.parse_error = "没有可用的原始文本，请重新上传"
                    await db.commit()
                    return

                registry = get_skill_registry()
                skill = registry.get_skill("resume-parsing")
                if not skill:
                    resume.parse_status = "FAILED"
                    resume.parse_error = "resume-parsing skill not found"
                    await db.commit()
                    return

                resume.parse_status = "PARSING"
                resume.parse_error = None
                await db.commit()

                start_time = datetime.utcnow()
                skill_input = {
                    "raw_text": resume.raw_text[:3000],
                    "file_name": resume.file_name,
                }

                try:
                    result = await skill.execute(skill_input)
                except Exception as e:
                    logger.error(f"Background parse LLM error for {resume_id}: {e}")
                    elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    resume.parse_status = "FAILED"
                    resume.parse_error = f"LLM调用失败: {str(e)[:200]}"
                    resume.parse_time_ms = elapsed_ms
                    await db.commit()
                    return

                elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

                exec_log = SkillExecutionLog(
                    skill_id=skill.skill_id,
                    version=skill.version,
                    task_id=resume.resume_id,
                    input_params={"file_name": resume.file_name},
                    output_result=result.output if result.success else None,
                    execution_status=result.status.value,
                    execution_time_ms=elapsed_ms,
                    validation_score=result.validation_score,
                    error_message=result.error_message,
                    executed_at=start_time,
                )
                db.add(exec_log)

                if not result.success or not result.output:
                    resume.parse_status = "FAILED"
                    resume.parse_error = result.error_message or "解析失败"
                    resume.parse_time_ms = elapsed_ms
                    await db.commit()
                    return

                output = result.output
                resume.candidate_name = output.get("candidate_name")
                resume.phone = output.get("phone")
                resume.email = output.get("email")
                resume.parsing_skill_id = skill.skill_id
                resume.parsing_skill_version = skill.version
                resume.parse_time_ms = elapsed_ms
                resume.parsed_content = {
                    "summary": output.get("summary"),
                    "education": output.get("education", []),
                    "work_experience": output.get("work_experience", []),
                    "project_experience": output.get("project_experience", []),
                    "skills": output.get("skills", []),
                }
                resume.parse_status = "PARSED"
                resume.parse_error = None
                await db.commit()
                logger.info(f"Background parse completed for {resume_id} in {elapsed_ms}ms")

            except Exception as e:
                logger.error(f"Background parse failed for {resume_id}: {e}", exc_info=True)
                try:
                    result = await db.execute(select(Resume).where(Resume.resume_id == resume_id))
                    resume = result.scalar_one_or_none()
                    if resume:
                        resume.parse_status = "FAILED"
                        resume.parse_error = f"后台解析异常: {str(e)[:200]}"
                        await db.commit()
                except Exception:
                    pass
