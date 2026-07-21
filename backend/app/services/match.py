"""S4-06 MatchService：单点/批量人岗匹配、查询与排行。

- 单点匹配走 `jd-candidate-matching` Skill，overall_score 由 Service 层按权重重算：
  `round(0.5*skill + 0.3*experience + 0.2*education, 1)`。
- 批量匹配在内存维护任务状态字典，使用独立 session + Semaphore 限并发后台执行。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.skill_registry import get_skill_registry
from app.core.config import get_settings
from app.core.time import _to_naive_utc, utcnow_aware, utcnow_naive
from app.models import JD, MatchScore, Resume, Skill, SkillExecutionLog

logger = logging.getLogger(__name__)

_MATCHING_SKILL_ID = "jd-candidate-matching"
_MATCHING_SKILL_NAME = "JD候选人匹配"

# 权重（技能 0.5 / 经验 0.3 / 学历 0.2）
_W_SKILL = 0.5
_W_EXPERIENCE = 0.3
_W_EDUCATION = 0.2

# 批量任务状态（跨请求共享的进程内字典）
_BATCH_TASKS: dict[str, dict[str, Any]] = {}
_BATCH_TASK_REFS: set[asyncio.Task] = set()


class MatchNotFoundError(ValueError):
    """JD 或简历不存在（API 层映射为 404）。"""


class ResumeNotParsedError(ValueError):
    """简历尚未解析完成，不允许评分（API 层映射为 409）。"""


class MatchSkillError(RuntimeError):
    """匹配 Skill 执行失败（API 层映射为 500）。"""


@dataclass
class BatchTaskHandle:
    task_id: str
    jd_id: str
    total_submitted: int
    submitted_at: datetime


class MatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    async def _get_jd(self, jd_id: str) -> JD | None:
        result = await self.db.execute(select(JD).where(JD.jd_id == jd_id))
        return result.scalar_one_or_none()

    async def _get_resume(self, resume_id: str) -> Resume | None:
        result = await self.db.execute(select(Resume).where(Resume.resume_id == resume_id))
        return result.scalar_one_or_none()

    async def get_score(self, score_id: str) -> MatchScore | None:
        result = await self.db.execute(select(MatchScore).where(MatchScore.score_id == score_id))
        return result.scalar_one_or_none()

    async def get_score_by_pair(self, jd_id: str, resume_id: str) -> MatchScore | None:
        result = await self.db.execute(
            select(MatchScore).where(MatchScore.jd_id == jd_id, MatchScore.resume_id == resume_id)
        )
        return result.scalar_one_or_none()

    async def rank_by_jd(self, jd_id: str, *, limit: int = 20, offset: int = 0) -> tuple[list[MatchScore], int]:
        total_result = await self.db.execute(
            select(func.count()).select_from(MatchScore).where(MatchScore.jd_id == jd_id)
        )
        total = total_result.scalar_one()
        result = await self.db.execute(
            select(MatchScore)
            .where(MatchScore.jd_id == jd_id)
            .order_by(desc(MatchScore.overall_score))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def rank_by_jd_items(
        self, jd_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """排行 + 候选人名 + is_stale，供排名端点直接序列化。"""
        scores, total = await self.rank_by_jd(jd_id, limit=limit, offset=offset)
        jd = await self._get_jd(jd_id)
        jd_updated = jd.updated_at if jd else None

        name_map: dict[str, str | None] = {}
        upd_map: dict[str, datetime | None] = {}
        ids = [s.resume_id for s in scores]
        if ids:
            res = await self.db.execute(
                select(Resume.resume_id, Resume.candidate_name, Resume.updated_at).where(Resume.resume_id.in_(ids))
            )
            for rid, name, upd in res.all():
                name_map[rid] = name
                upd_map[rid] = upd

        items = [
            {
                "score_id": s.score_id,
                "resume_id": s.resume_id,
                "candidate_name": name_map.get(s.resume_id),
                "overall_score": s.overall_score,
                "dimension_scores": s.dimension_scores,
                "is_stale": self.is_stale(s, jd_updated_at=jd_updated, resume_updated_at=upd_map.get(s.resume_id)),
                "created_at": s.created_at,
            }
            for s in scores
        ]
        return items, total

    async def list_by_resume(self, resume_id: str, *, limit: int = 20) -> list[MatchScore]:
        result = await self.db.execute(
            select(MatchScore)
            .where(MatchScore.resume_id == resume_id)
            .order_by(desc(MatchScore.overall_score))
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # 陈旧判断
    # ------------------------------------------------------------------
    def is_stale(
        self,
        score: MatchScore,
        *,
        jd_updated_at: datetime | None = None,
        resume_updated_at: datetime | None = None,
    ) -> bool:
        snap_r = _to_naive_utc(score.resume_updated_at_snapshot)
        snap_j = _to_naive_utc(score.jd_updated_at_snapshot)
        r = _to_naive_utc(resume_updated_at)
        j = _to_naive_utc(jd_updated_at)
        if snap_r is not None and r is not None and r > snap_r:
            return True
        if snap_j is not None and j is not None and j > snap_j:
            return True
        return False

    async def compute_is_stale(self, score: MatchScore) -> bool:
        jd = await self._get_jd(score.jd_id)
        resume = await self._get_resume(score.resume_id)
        return self.is_stale(
            score,
            jd_updated_at=jd.updated_at if jd else None,
            resume_updated_at=resume.updated_at if resume else None,
        )

    # ------------------------------------------------------------------
    # 单点匹配
    # ------------------------------------------------------------------
    async def _ensure_skill_registered(self, skill_id: str, version: str) -> None:
        """确保 skills 表存在对应记录，满足 skill_execution_logs 的外键约束。"""
        result = await self.db.execute(select(Skill).where(Skill.skill_id == skill_id))
        if result.scalar_one_or_none() is None:
            self.db.add(
                Skill(
                    skill_id=skill_id,
                    skill_name=_MATCHING_SKILL_NAME,
                    current_version=version,
                    status="ACTIVE",
                )
            )
            await self.db.flush()

    async def match_one(self, jd_id: str, resume_id: str, *, force: bool = False) -> MatchScore:
        jd = await self._get_jd(jd_id)
        if jd is None:
            raise MatchNotFoundError(f"JD not found: {jd_id}")
        resume = await self._get_resume(resume_id)
        if resume is None:
            raise MatchNotFoundError(f"Resume not found: {resume_id}")
        if resume.parse_status != "PARSED":
            raise ResumeNotParsedError(f"Resume not parsed yet: {resume_id} (status={resume.parse_status})")

        existing = await self.get_score_by_pair(jd_id, resume_id)
        if existing is not None and not force:
            return existing

        registry = get_skill_registry()
        skill = registry.get_skill(_MATCHING_SKILL_ID)
        if skill is None:
            raise MatchSkillError(f"{_MATCHING_SKILL_ID} skill not found in registry")

        skill_input = {
            "jd": {
                "title": jd.title,
                "summary": jd.summary or "",
                "requirements": jd.requirements or [],
                "required_skills": jd.required_skills or [],
                "preferred_skills": jd.preferred_skills or [],
                "experience_years": jd.experience_years or "",
                "education_requirement": jd.education_requirement or "",
            },
            "resume": {
                "candidate_name": resume.candidate_name or "",
                "parsed_content": resume.parsed_content or {},
            },
        }

        result = await skill.execute(skill_input)

        await self._ensure_skill_registered(skill.skill_id, skill.version)
        exec_log = SkillExecutionLog(
            skill_id=skill.skill_id,
            version=skill.version,
            task_id=resume_id,
            input_params={"jd_id": jd_id, "resume_id": resume_id},
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
            raise MatchSkillError(f"matching skill failed: {result.error_message}")

        output = result.output
        sm = output["skill_match"]
        em = output["experience_match"]
        edm = output["education_match"]
        overall = round(
            _W_SKILL * float(sm["score"]) + _W_EXPERIENCE * float(em["score"]) + _W_EDUCATION * float(edm["score"]),
            1,
        )
        dimension = {
            "skill_match": sm,
            "experience_match": em,
            "education_match": edm,
            "overall_reasoning": output.get("overall_reasoning", ""),
        }
        now = utcnow_naive()

        if existing is not None:
            existing.overall_score = overall
            existing.dimension_scores = dimension
            existing.matching_skill_id = skill.skill_id
            existing.matching_skill_version = skill.version
            existing.skill_execution_id = exec_log.execution_id
            existing.resume_updated_at_snapshot = resume.updated_at
            existing.jd_updated_at_snapshot = jd.updated_at
            existing.status = "COMPLETED"
            existing.error_message = None
            existing.updated_at = now
            score = existing
        else:
            score = MatchScore(
                jd_id=jd_id,
                resume_id=resume_id,
                overall_score=overall,
                dimension_scores=dimension,
                matching_skill_id=skill.skill_id,
                matching_skill_version=skill.version,
                skill_execution_id=exec_log.execution_id,
                resume_updated_at_snapshot=resume.updated_at,
                jd_updated_at_snapshot=jd.updated_at,
                status="COMPLETED",
                created_at=now,
                updated_at=now,
            )
            self.db.add(score)
        await self.db.flush()

        exec_log.task_id = score.score_id
        await self.db.flush()
        await self.db.commit()
        return score

    # ------------------------------------------------------------------
    # 批量匹配
    # ------------------------------------------------------------------
    async def batch_match(
        self,
        jd_id: str,
        *,
        resume_ids: list[str] | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> BatchTaskHandle:
        jd = await self._get_jd(jd_id)
        if jd is None:
            raise MatchNotFoundError(f"JD not found: {jd_id}")

        if resume_ids is None:
            query = (
                select(Resume.resume_id)
                .where(
                    Resume.parse_status == "PARSED",
                    Resume.dedup_status.in_(["NONE", "IGNORED"]),
                )
                .order_by(desc(Resume.created_at))
            )
            if limit is not None:
                query = query.limit(limit)
            result = await self.db.execute(query)
            targets = list(result.scalars().all())
        else:
            targets = list(resume_ids)
            if limit is not None:
                targets = targets[:limit]

        task_id = f"batch_{uuid.uuid4().hex[:12]}"
        now = utcnow_aware()
        _BATCH_TASKS[task_id] = {
            "task_id": task_id,
            "jd_id": jd_id,
            "total": len(targets),
            "completed": 0,
            "failed": 0,
            "status": "PENDING",
            "started_at": now,
            "finished_at": None,
            "resume_ids": targets,
            "force": force,
        }

        if targets:
            task = asyncio.create_task(self._run_batch(task_id))
            _BATCH_TASK_REFS.add(task)
            task.add_done_callback(_BATCH_TASK_REFS.discard)
        else:
            _BATCH_TASKS[task_id]["status"] = "COMPLETED"
            _BATCH_TASKS[task_id]["finished_at"] = now

        return BatchTaskHandle(task_id=task_id, jd_id=jd_id, total_submitted=len(targets), submitted_at=now)

    async def _run_batch(self, task_id: str) -> None:
        state = _BATCH_TASKS.get(task_id)
        if state is None:
            return
        state["status"] = "RUNNING"

        settings = get_settings()
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        semaphore = asyncio.Semaphore(4)

        async def _one(resume_id: str) -> None:
            async with semaphore:
                try:
                    async with factory() as session:
                        service = MatchService(session)
                        await service.match_one(state["jd_id"], resume_id, force=state["force"])
                    state["completed"] += 1
                except Exception as exc:  # noqa: BLE001 - 后台批量单条失败不影响整体
                    state["failed"] += 1
                    logger.warning("batch match failed for %s: %s", resume_id, exc)

        try:
            await asyncio.gather(*[_one(r) for r in state["resume_ids"]])
        finally:
            state["status"] = "COMPLETED"
            state["finished_at"] = utcnow_aware()
            await engine.dispose()

    def get_batch_status(self, task_id: str) -> dict[str, Any] | None:
        return _BATCH_TASKS.get(task_id)
