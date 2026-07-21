"""S4-02 模型层测试（TEST-PLAN §2）。"""

import pytest
from factories import build_jd, build_resume
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MatchScore
from app.models.match_score import generate_match_score_id

_DIM = {
    "skill_match": {"score": 80, "rationale": "ok", "matched": ["Python"], "missing": []},
    "experience_match": {"score": 70, "rationale": "ok", "years_required": "3", "years_actual": "4"},
    "education_match": {"score": 90, "rationale": "ok", "required": "本科", "actual": "硕士"},
    "overall_reasoning": "综合良好",
}


def test_match_score_id_default_prefix() -> None:
    ms_id = generate_match_score_id()
    assert ms_id.startswith("ms_")
    assert len(ms_id) == 15


async def test_match_score_creates_with_defaults(db_session: AsyncSession) -> None:
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()
    ms = MatchScore(jd_id=jd.jd_id, resume_id=resume.resume_id, overall_score=79.0, dimension_scores=_DIM)
    db_session.add(ms)
    await db_session.flush()
    assert ms.score_id.startswith("ms_")
    assert ms.status == "COMPLETED"


async def test_match_score_unique_pair_constraint(db_session: AsyncSession) -> None:
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()
    db_session.add(MatchScore(jd_id=jd.jd_id, resume_id=resume.resume_id, overall_score=80.0, dimension_scores=_DIM))
    await db_session.flush()
    db_session.add(MatchScore(jd_id=jd.jd_id, resume_id=resume.resume_id, overall_score=70.0, dimension_scores=_DIM))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_match_score_cascade_on_resume_delete(db_session: AsyncSession) -> None:
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()
    ms = MatchScore(jd_id=jd.jd_id, resume_id=resume.resume_id, overall_score=80.0, dimension_scores=_DIM)
    db_session.add(ms)
    await db_session.flush()
    score_id = ms.score_id
    await db_session.delete(resume)
    await db_session.flush()
    db_session.expire_all()
    row = (await db_session.execute(select(MatchScore).where(MatchScore.score_id == score_id))).scalar_one_or_none()
    assert row is None
