"""S4-07/S4-08 排名与简历匹配列表 API 集成测试（TEST-PLAN §6）。"""
from factories import build_jd, build_resume
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MatchScore

_DIM = {
    "skill_match": {"score": 80, "rationale": "ok", "matched": ["Python"], "missing": []},
    "experience_match": {"score": 70, "rationale": "ok", "years_required": "3", "years_actual": "4"},
    "education_match": {"score": 90, "rationale": "ok", "required": "本科", "actual": "硕士"},
    "overall_reasoning": "综合良好",
}


async def test_jd_ranking_orders_desc(client_db: AsyncClient, db_session: AsyncSession) -> None:
    jd = build_jd()
    r1 = build_resume(candidate_name="A")
    r2 = build_resume(candidate_name="B")
    r3 = build_resume(candidate_name="C")
    db_session.add_all([jd, r1, r2, r3])
    await db_session.flush()
    for r, sc in [(r1, 60.0), (r2, 95.0), (r3, 80.0)]:
        db_session.add(
            MatchScore(jd_id=jd.jd_id, resume_id=r.resume_id, overall_score=sc, dimension_scores=_DIM)
        )
    await db_session.flush()

    resp = await client_db.get(f"/api/v1/jds/{jd.jd_id}/ranking")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert [i["overall_score"] for i in data["items"]] == [95.0, 80.0, 60.0]
    assert data["items"][0]["candidate_name"] == "B"


async def test_jd_ranking_pagination(client_db: AsyncClient, db_session: AsyncSession) -> None:
    jd = build_jd()
    r1, r2, r3 = build_resume(), build_resume(), build_resume()
    db_session.add_all([jd, r1, r2, r3])
    await db_session.flush()
    for r, sc in [(r1, 60.0), (r2, 95.0), (r3, 80.0)]:
        db_session.add(
            MatchScore(jd_id=jd.jd_id, resume_id=r.resume_id, overall_score=sc, dimension_scores=_DIM)
        )
    await db_session.flush()

    resp = await client_db.get(f"/api/v1/jds/{jd.jd_id}/ranking?limit=1&offset=1")
    assert resp.status_code == 200
    assert [i["overall_score"] for i in resp.json()["items"]] == [80.0]


async def test_resume_matches_returns_multi_jds(
    client_db: AsyncClient, db_session: AsyncSession
) -> None:
    jd1, jd2 = build_jd(), build_jd()
    resume = build_resume()
    db_session.add_all([jd1, jd2, resume])
    await db_session.flush()
    db_session.add(
        MatchScore(jd_id=jd1.jd_id, resume_id=resume.resume_id, overall_score=70.0, dimension_scores=_DIM)
    )
    db_session.add(
        MatchScore(jd_id=jd2.jd_id, resume_id=resume.resume_id, overall_score=88.0, dimension_scores=_DIM)
    )
    await db_session.flush()

    resp = await client_db.get(f"/api/v1/resumes/{resume.resume_id}/matches")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["overall_score"] == 88.0
