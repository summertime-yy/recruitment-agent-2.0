from factories import build_jd, build_resume, build_skill, build_skill_execution_log
from sqlalchemy.ext.asyncio import AsyncSession


async def test_factories_build_valid_resume(db_session: AsyncSession) -> None:
    r = build_resume()
    db_session.add(r)
    await db_session.flush()
    assert r.resume_id.startswith("res_")
    assert r.parse_status == "PARSED"
    assert r.candidate_name == "张三"


async def test_factories_build_valid_jd(db_session: AsyncSession) -> None:
    j = build_jd()
    db_session.add(j)
    await db_session.flush()
    assert j.jd_id
    assert j.title


async def test_factories_build_skill_execution_log(db_session: AsyncSession) -> None:
    db_session.add(build_skill())
    await db_session.flush()
    log = build_skill_execution_log()
    db_session.add(log)
    await db_session.flush()
    assert log.execution_id is not None
    assert log.skill_id == "jd-candidate-matching"
