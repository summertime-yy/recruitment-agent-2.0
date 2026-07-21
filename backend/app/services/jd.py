import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skill_registry import get_skill_registry
from app.core.time import utcnow_naive
from app.models import JD, SkillExecutionLog
from app.schemas import JDGenerateRequest, JDUpdateRequest


class JDService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _generate_id(prefix: str = "jd") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    async def generate_jd(self, request: JDGenerateRequest) -> tuple[JD, SkillExecutionLog]:
        registry = get_skill_registry()
        skill = registry.get_skill("jd-generation")
        if not skill:
            raise RuntimeError("jd-generation skill not found in registry")

        skill_input = {
            "title": request.title,
            "department": request.department or "",
            "level": request.level or "",
            "location": request.location or "",
            "job_type": request.job_type or "全职",
            "recruit_type": request.recruit_type or "社招",
            "headcount": request.headcount or 1,
            "experience_years": request.experience_years or "",
            "education_requirement": request.education_requirement or "",
            "salary_range": request.salary_range or "",
            "description": request.description,
            "requirements": request.requirements or [],
            "required_skills": request.required_skills or [],
            "preferred_skills": request.preferred_skills or [],
        }

        result = await skill.execute(skill_input)

        exec_log = SkillExecutionLog(
            skill_id=skill.skill_id,
            version=skill.version,
            task_id=None,
            user_id=request.created_by,
            input_params=skill_input,
            output_result=result.output if result.success else None,
            execution_status=result.status.value,
            execution_time_ms=result.execution_time_ms,
            validation_score=result.validation_score,
            error_message=result.error_message,
            executed_at=utcnow_naive(),
        )
        self.db.add(exec_log)
        await self.db.flush()

        if not result.success or not result.output:
            await self.db.commit()
            raise RuntimeError(f"JD generation failed: {result.error_message}")

        output = result.output
        jd = JD(
            jd_id=self._generate_id(),
            title=output.get("title", request.title),
            department=output.get("department") or request.department,
            level=output.get("level") or request.level,
            location=output.get("location") or request.location,
            job_type=output.get("job_type") or request.job_type or "全职",
            recruit_type=output.get("recruit_type") or request.recruit_type or "社招",
            headcount=output.get("headcount") or request.headcount or 1,
            experience_years=output.get("experience_years") or request.experience_years,
            education_requirement=output.get("education_requirement") or request.education_requirement,
            salary_range=output.get("salary_range") or request.salary_range,
            summary=output.get("summary"),
            responsibilities=output.get("responsibilities"),
            requirements=output.get("requirements"),
            required_skills=output.get("required_skills"),
            preferred_skills=output.get("preferred_skills"),
            compliance_check={"passed": True, "issues": []},
            template_id=None,
            created_by=request.created_by,
            status="DRAFT",
            created_at=utcnow_naive(),
            updated_at=utcnow_naive(),
        )
        self.db.add(jd)
        await self.db.flush()

        exec_log.task_id = jd.jd_id
        await self.db.commit()
        await self.db.refresh(jd)
        await self.db.refresh(exec_log)

        return jd, exec_log

    async def get_jd(self, jd_id: str) -> JD | None:
        result = await self.db.execute(select(JD).where(JD.jd_id == jd_id))
        return result.scalar_one_or_none()

    async def list_jds(
        self,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[JD], int]:
        query = select(JD)
        count_query = select(JD)

        if status:
            query = query.where(JD.status == status)
            count_query = count_query.where(JD.status == status)

        if keyword:
            query = query.where(JD.title.ilike(f"%{keyword}%"))
            count_query = count_query.where(JD.title.ilike(f"%{keyword}%"))

        total_result = await self.db.execute(count_query.with_only_columns(JD.jd_id))
        total = len(total_result.fetchall())

        query = query.order_by(desc(JD.created_at)).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_jd(self, jd_id: str, update_data: JDUpdateRequest) -> JD | None:
        jd = await self.get_jd(jd_id)
        if not jd:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(jd, field, value)
        jd.updated_at = utcnow_naive()

        await self.db.commit()
        await self.db.refresh(jd)
        return jd

    async def delete_jd(self, jd_id: str) -> bool:
        jd = await self.get_jd(jd_id)
        if not jd:
            return False
        await self.db.delete(jd)
        await self.db.commit()
        return True
