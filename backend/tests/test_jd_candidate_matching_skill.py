"""S4-04 Skill 单测（TEST-PLAN §3）。

通过 monkeypatch 打桩 app.agent.llm_adapter.call_llm_json（execute 内部局部 import，
故对模块属性打桩即可生效），断言输入渲染、输出校验、合规校验路径。
"""

from app.agent.skill_registry import get_skill_registry

VALID_OUTPUT = {
    "skill_match": {"score": 80, "rationale": "技能匹配良好", "matched": ["Python"], "missing": []},
    "experience_match": {
        "score": 70,
        "rationale": "经验尚可",
        "years_required": "3-5年",
        "years_actual": "4年",
    },
    "education_match": {"score": 90, "rationale": "学历达标", "required": "本科", "actual": "硕士"},
    "overall_reasoning": "综合匹配度较高，建议进入面试",
}

JD_INPUT = {
    "jd": {
        "title": "高级后端工程师",
        "requirements": ["5年以上后端经验"],
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Kubernetes"],
        "experience_years": "3-5年",
        "education_requirement": "本科及以上",
    },
    "resume": {
        "candidate_name": "张三",
        "parsed_content": {"skills": ["Python", "FastAPI"], "summary": "4年后端经验"},
    },
}


def _skill():
    return get_skill_registry().get_skill("jd-candidate-matching")


def test_skill_is_registered() -> None:
    skill = _skill()
    assert skill is not None
    assert skill.version == "1.0.0"


def test_skill_max_retries_is_zero() -> None:
    assert _skill().max_retries == 0


async def test_skill_input_schema_rejects_missing_jd() -> None:
    result = await _skill().execute({"resume": JD_INPUT["resume"]})
    assert result.success is False
    assert result.status.value == "FAILED"


async def test_skill_prompt_renders_jd_and_resume_fields(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def _fake(system_prompt: str, user_prompt: str) -> dict:
        captured["user"] = user_prompt
        return VALID_OUTPUT

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)
    await _skill().execute(JD_INPUT)
    assert "高级后端工程师" in captured["user"]
    assert "张三" in captured["user"]
    assert "Python" in captured["user"]


async def test_skill_success_returns_all_dimensions(monkeypatch) -> None:
    async def _fake(system_prompt: str, user_prompt: str) -> dict:
        return VALID_OUTPUT

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)
    result = await _skill().execute(JD_INPUT)
    assert result.success is True
    for dim in ("skill_match", "experience_match", "education_match"):
        assert 0 <= result.output[dim]["score"] <= 100


async def test_skill_rejects_out_of_range_score(monkeypatch) -> None:
    bad = {**VALID_OUTPUT, "skill_match": {"score": 150, "rationale": "x", "matched": [], "missing": []}}

    async def _fake(system_prompt: str, user_prompt: str) -> dict:
        return bad

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)
    result = await _skill().execute(JD_INPUT)
    assert result.success is False


async def test_skill_compliance_ok_when_output_clean(monkeypatch) -> None:
    async def _fake(system_prompt: str, user_prompt: str) -> dict:
        return VALID_OUTPUT

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)
    result = await _skill().execute(JD_INPUT)
    compliance = _skill().compliance_check(result.output)
    assert compliance["passed"] is True
