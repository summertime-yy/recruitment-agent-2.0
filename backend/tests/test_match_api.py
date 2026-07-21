"""S4-07 API 集成测试（TEST-PLAN §6）：/match-scores 路由。"""

from factories import build_jd, build_resume
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _patch_llm(monkeypatch, *, skill=80, exp=70, edu=90):
    async def _fake(system_prompt: str, user_prompt: str) -> dict:
        return {
            "skill_match": {"score": skill, "rationale": "r", "matched": ["Python"], "missing": []},
            "experience_match": {"score": exp, "rationale": "r", "years_required": "3", "years_actual": "4"},
            "education_match": {"score": edu, "rationale": "r", "required": "本科", "actual": "硕士"},
            "overall_reasoning": "综合评价",
        }

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)


async def test_post_match_score_returns_201(client_db: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    resp = await client_db.post("/api/v1/match-scores", json={"jd_id": jd.jd_id, "resume_id": resume.resume_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["overall_score"] == 79.0
    assert data["dimension_scores"]["skill_match"]["score"] == 80
    assert data["status"] == "COMPLETED"


async def test_post_match_score_404_when_jd_missing(
    client_db: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_llm(monkeypatch)
    resume = build_resume()
    db_session.add(resume)
    await db_session.flush()

    resp = await client_db.post("/api/v1/match-scores", json={"jd_id": "jd_none", "resume_id": resume.resume_id})
    assert resp.status_code == 404


async def test_post_match_score_404_when_resume_missing(
    client_db: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    await db_session.flush()

    resp = await client_db.post("/api/v1/match-scores", json={"jd_id": jd.jd_id, "resume_id": "res_none"})
    assert resp.status_code == 404


async def test_post_match_score_409_when_resume_not_parsed(
    client_db: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume(parse_status="PARSING")
    db_session.add_all([jd, resume])
    await db_session.flush()

    resp = await client_db.post("/api/v1/match-scores", json={"jd_id": jd.jd_id, "resume_id": resume.resume_id})
    assert resp.status_code == 409


async def test_post_match_score_idempotent_without_force(
    client_db: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    body = {"jd_id": jd.jd_id, "resume_id": resume.resume_id}
    r1 = await client_db.post("/api/v1/match-scores", json=body)
    r2 = await client_db.post("/api/v1/match-scores", json=body)
    assert r1.json()["score_id"] == r2.json()["score_id"]


async def test_post_match_score_force_recomputes(client_db: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch, skill=80, exp=70, edu=90)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    body = {"jd_id": jd.jd_id, "resume_id": resume.resume_id}
    r1 = await client_db.post("/api/v1/match-scores", json=body)
    first = r1.json()

    _patch_llm(monkeypatch, skill=60, exp=60, edu=60)
    r2 = await client_db.post("/api/v1/match-scores", json={**body, "force": True})
    second = r2.json()
    assert second["score_id"] == first["score_id"]
    assert second["overall_score"] == 60.0


async def test_post_batch_match_returns_task_id(client_db: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    db_session.add_all([build_resume() for _ in range(2)])
    await db_session.flush()

    resp = await client_db.post("/api/v1/match-scores/batch", json={"jd_id": jd.jd_id, "limit": 2})
    assert resp.status_code == 202
    assert "task_id" in resp.json()


async def test_get_batch_status_transitions(client_db: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    db_session.add_all([build_resume() for _ in range(2)])
    await db_session.flush()

    resp = await client_db.post("/api/v1/match-scores/batch", json={"jd_id": jd.jd_id, "limit": 2})
    task_id = resp.json()["task_id"]
    status_resp = await client_db.get(f"/api/v1/match-scores/batch/{task_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in ("PENDING", "RUNNING", "COMPLETED")


async def test_get_score_by_id_returns_row(client_db: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    created = await client_db.post("/api/v1/match-scores", json={"jd_id": jd.jd_id, "resume_id": resume.resume_id})
    score_id = created.json()["score_id"]

    resp = await client_db.get(f"/api/v1/match-scores/{score_id}")
    assert resp.status_code == 200
    assert resp.json()["score_id"] == score_id


async def test_get_score_by_id_404(client_db: AsyncClient) -> None:
    resp = await client_db.get("/api/v1/match-scores/ms_nonexistent")
    assert resp.status_code == 404


async def test_routes_order_specific_before_dynamic(client_db: AsyncClient) -> None:
    resp = await client_db.get("/api/v1/match-scores/batch/unknown_task")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "batch task not found"
