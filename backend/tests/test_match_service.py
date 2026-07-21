"""S4-06 MatchService 单测（TEST-PLAN §5）。

使用 db_session（PostgreSQL 事务回滚）+ monkeypatch 打桩 call_llm_json。
"""

from datetime import UTC, datetime, timedelta

import pytest
from factories import build_jd, build_resume
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MatchScore, SkillExecutionLog
from app.services.match import MatchService

_DIM = {
    "skill_match": {"score": 80, "rationale": "ok", "matched": ["Python"], "missing": []},
    "experience_match": {"score": 70, "rationale": "ok", "years_required": "3", "years_actual": "4"},
    "education_match": {"score": 90, "rationale": "ok", "required": "本科", "actual": "硕士"},
    "overall_reasoning": "综合良好",
}


def _patch_llm(monkeypatch, *, skill=80, exp=70, edu=90, counter=None):
    async def _fake(system_prompt: str, user_prompt: str) -> dict:
        if counter is not None:
            counter["n"] += 1
        return {
            "skill_match": {"score": skill, "rationale": "r", "matched": ["Python"], "missing": []},
            "experience_match": {"score": exp, "rationale": "r", "years_required": "3", "years_actual": "4"},
            "education_match": {"score": edu, "rationale": "r", "required": "本科", "actual": "硕士"},
            "overall_reasoning": "综合评价",
        }

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)
    return _fake


async def test_match_one_creates_row_when_first(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch, skill=80, exp=70, edu=90)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    score = await svc.match_one(jd.jd_id, resume.resume_id)

    assert isinstance(score, MatchScore)
    assert score.overall_score == 79.0  # round(0.5*80 + 0.3*70 + 0.2*90, 1)
    assert score.status == "COMPLETED"
    assert score.matching_skill_id == "jd-candidate-matching"


async def test_match_one_returns_cached_when_not_force(db_session: AsyncSession, monkeypatch) -> None:
    counter = {"n": 0}
    _patch_llm(monkeypatch, counter=counter)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    s1 = await svc.match_one(jd.jd_id, resume.resume_id)
    assert counter["n"] == 1
    s2 = await svc.match_one(jd.jd_id, resume.resume_id)
    assert counter["n"] == 1  # LLM 未被再次调用
    assert s2.score_id == s1.score_id
    assert s2.skill_execution_id == s1.skill_execution_id


async def test_match_one_recomputes_when_force_true(db_session: AsyncSession, monkeypatch) -> None:
    counter = {"n": 0}
    _patch_llm(monkeypatch, skill=80, exp=70, edu=90, counter=counter)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    s1 = await svc.match_one(jd.jd_id, resume.resume_id)
    old_exec = s1.skill_execution_id
    assert s1.overall_score == 79.0

    _patch_llm(monkeypatch, skill=60, exp=60, edu=60, counter=counter)
    s2 = await svc.match_one(jd.jd_id, resume.resume_id, force=True)

    assert counter["n"] == 2
    assert s2.score_id == s1.score_id
    assert s2.skill_execution_id != old_exec
    assert s2.overall_score == 60.0


async def test_match_one_rejects_unparsed_resume(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume(parse_status="PARSING")
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    with pytest.raises(ValueError):
        await svc.match_one(jd.jd_id, resume.resume_id)


async def test_match_one_missing_jd_raises(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    resume = build_resume()
    db_session.add(resume)
    await db_session.flush()

    svc = MatchService(db_session)
    with pytest.raises(ValueError):
        await svc.match_one("jd_nonexistent", resume.resume_id)


async def test_match_one_missing_resume_raises(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    await db_session.flush()

    svc = MatchService(db_session)
    with pytest.raises(ValueError):
        await svc.match_one(jd.jd_id, "res_nonexistent")


async def test_match_one_writes_skill_execution_log(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    score = await svc.match_one(jd.jd_id, resume.resume_id)

    res = await db_session.execute(
        select(SkillExecutionLog).where(SkillExecutionLog.skill_id == "jd-candidate-matching")
    )
    logs = list(res.scalars().all())
    assert len(logs) >= 1
    assert score.skill_execution_id is not None
    assert logs[0].task_id == score.score_id


async def test_overall_score_uses_weighted_average(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch, skill=100, exp=50, edu=50)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    score = await svc.match_one(jd.jd_id, resume.resume_id)
    assert score.overall_score == 75.0  # round(0.5*100 + 0.3*50 + 0.2*50, 1)


async def test_is_stale_when_resume_updated_after_score(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    resume = build_resume()
    db_session.add_all([jd, resume])
    await db_session.flush()

    svc = MatchService(db_session)
    score = await svc.match_one(jd.jd_id, resume.resume_id)

    later = datetime.now(UTC) + timedelta(days=1)
    assert svc.is_stale(score, jd_updated_at=jd.updated_at, resume_updated_at=later) is True
    assert (
        svc.is_stale(
            score,
            jd_updated_at=score.jd_updated_at_snapshot,
            resume_updated_at=score.resume_updated_at_snapshot,
        )
        is False
    )


async def test_batch_match_default_selects_parsed_only(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    parsed = [build_resume() for _ in range(3)]
    pending = [build_resume(parse_status="PENDING") for _ in range(2)]
    db_session.add_all(parsed + pending)
    await db_session.flush()

    parsed_ids = {r.resume_id for r in parsed}
    pending_ids = {r.resume_id for r in pending}

    svc = MatchService(db_session)
    handle = await svc.batch_match(jd.jd_id)
    selected = set(svc.get_batch_status(handle.task_id)["resume_ids"])
    # 默认仅选 PARSED：3 条已解析均入选，2 条待解析均被排除
    assert parsed_ids <= selected
    assert not (pending_ids & selected)


async def test_batch_match_respects_limit(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    db_session.add_all([build_resume() for _ in range(4)])
    await db_session.flush()

    svc = MatchService(db_session)
    handle = await svc.batch_match(jd.jd_id, limit=2)
    assert handle.total_submitted == 2


async def test_batch_match_returns_task_handle(db_session: AsyncSession, monkeypatch) -> None:
    _patch_llm(monkeypatch)
    jd = build_jd()
    db_session.add(jd)
    db_session.add_all([build_resume() for _ in range(2)])
    await db_session.flush()

    svc = MatchService(db_session)
    handle = await svc.batch_match(jd.jd_id)
    state = svc.get_batch_status(handle.task_id)
    assert state is not None
    assert state["status"] in ("PENDING", "RUNNING", "COMPLETED")


async def test_rank_by_jd_orders_desc(db_session: AsyncSession) -> None:
    jd = build_jd()
    r1, r2, r3 = build_resume(), build_resume(), build_resume()
    db_session.add_all([jd, r1, r2, r3])
    await db_session.flush()
    for r, sc in [(r1, 60.0), (r2, 90.0), (r3, 75.0)]:
        db_session.add(MatchScore(jd_id=jd.jd_id, resume_id=r.resume_id, overall_score=sc, dimension_scores=_DIM))
    await db_session.flush()

    svc = MatchService(db_session)
    scores, total = await svc.rank_by_jd(jd.jd_id)
    assert total == 3
    assert [s.overall_score for s in scores] == [90.0, 75.0, 60.0]


async def test_list_by_resume_returns_all_jds(db_session: AsyncSession) -> None:
    jd1, jd2 = build_jd(), build_jd()
    resume = build_resume()
    db_session.add_all([jd1, jd2, resume])
    await db_session.flush()
    db_session.add(MatchScore(jd_id=jd1.jd_id, resume_id=resume.resume_id, overall_score=70.0, dimension_scores=_DIM))
    db_session.add(MatchScore(jd_id=jd2.jd_id, resume_id=resume.resume_id, overall_score=85.0, dimension_scores=_DIM))
    await db_session.flush()

    svc = MatchService(db_session)
    items = await svc.list_by_resume(resume.resume_id)
    assert len(items) == 2
    assert items[0].overall_score == 85.0
