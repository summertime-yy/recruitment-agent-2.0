"""S5-04 · Tool Router TDD 测试（PR-11 交付物，绿态）。

归属 PR：PR-11（TASKS-STAGE5.md S5-04）
覆盖用例（TC-S5-04-1..6）：
- TC-S5-04-1  dispatch 路由到已注册的可分发 stub Skill（不触 LLM）
- TC-S5-04-2  dispatch 未知工具名 → UnknownToolError
- TC-S5-04-3  search_resumes 缺 keyword → ToolParamError；带 keyword + mock 返回 items 字典
- TC-S5-04-4  read_jd 不存在 jd_id → ToolParamError；存在 → 返回 JD dict
- TC-S5-04-5  dispatch 命中 internal Skill → SkillNotDispatchableError
- TC-S5-04-6  route_task_type 提取 task_type；缺失/None/空 → 'unknown'

约定：本文件全部用例不依赖真实 DB / LLM（内置工具通过 monkeypatch Service 实现隔离）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.agent.base_skill import BaseSkill, SkillResult
from app.agent.orchestrator.tool_router import (
    SkillNotDispatchableError,
    ToolParamError,
    ToolRouter,
    UnknownToolError,
    route_task_type,
)
from app.agent.skill_registry import SkillRegistry


# ---------------------------------------------------------------------------
# Stub Skills（避免触真实 LLM / 实现耦合，聚焦"路由"本身）
# ---------------------------------------------------------------------------
class _DispatchableStub(BaseSkill):
    """可分发 stub：覆盖 execute 直接返回，不调用 call_llm_json。"""

    def __init__(self):
        self.skill_dir = None
        self.metadata = None
        self._system_prompt = ""
        self._user_prompt_template = ""
        self._examples: list[dict[str, Any]] = []
        self._tool_chain: list[dict[str, Any]] = []
        self.skill_id = "stub-dispatch"
        self.skill_name = "stub"
        self.version = "1.0.0"
        self.internal = False
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(success=True, output={"routed": True, "input": input_params})


class _InternalStub(BaseSkill):
    """internal stub：Tool Router 不应直接分发。"""

    def __init__(self):
        self.skill_dir = None
        self.metadata = None
        self._system_prompt = ""
        self._user_prompt_template = ""
        self._examples: list[dict[str, Any]] = []
        self._tool_chain: list[dict[str, Any]] = []
        self.skill_id = "stub-internal"
        self.skill_name = "stub-internal"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        raise AssertionError("internal skill must not be dispatched by Tool Router")


# ---------------------------------------------------------------------------
# TC-S5-04-1
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc_s5_04_1_dispatch_routes_to_registered_skill():
    """dispatch 将 tool_name 路由到已注册的可分发 stub Skill，不触 LLM。"""
    reg = SkillRegistry()
    reg.register_skill(_DispatchableStub())
    router = ToolRouter(registry=reg)

    result = await router.dispatch("stub-dispatch", {"foo": "bar"})

    assert isinstance(result, SkillResult)
    assert result.success is True
    assert result.output == {"routed": True, "input": {"foo": "bar"}}


# ---------------------------------------------------------------------------
# TC-S5-04-2
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc_s5_04_2_dispatch_unknown_tool_raises():
    """未知 tool_name（非内置、非注册 Skill）→ UnknownToolError。"""
    router = ToolRouter(registry=SkillRegistry())
    with pytest.raises(UnknownToolError) as exc:
        await router.dispatch("totally-unknown-tool", {})
    assert exc.value.tool_name == "totally-unknown-tool"


# ---------------------------------------------------------------------------
# TC-S5-04-3
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc_s5_04_3_search_resumes_missing_keyword_and_success():
    """search_resumes 缺 keyword → ToolParamError；带 keyword + mock → 返回 items 字典。"""
    router = ToolRouter(registry=SkillRegistry())

    # 缺 keyword → ToolParamError（先于 db 校验，无需 db）
    with pytest.raises(ToolParamError):
        await router.dispatch("search_resumes", {})

    # mock ResumeService.list_resumes，验证返回结构
    class _FakeResume:
        def __init__(self):
            self.resume_id = "res_abc"
            self.candidate_name = "张三"
            self.parsed_content = {"skills": ["Python", "React"]}
            self.candidate_status = "NEW"
            self.created_at = datetime(2026, 7, 20, 12, 0, 0)

    class _FakeResumeService:
        def __init__(self, db):
            self.db = db

        async def list_resumes(self, **kwargs):
            assert kwargs["keyword"] == "Python"
            return [_FakeResume()], 1

    import app.agent.orchestrator.tool_router as tr_module

    orig = tr_module.ResumeService
    tr_module.ResumeService = _FakeResumeService
    try:
        result = await router.dispatch("search_resumes", {"keyword": "Python", "page": 1, "page_size": 10}, db=object())
    finally:
        tr_module.ResumeService = orig

    assert result.success is True
    assert result.output["total"] == 1
    assert result.output["page"] == 1
    assert result.output["page_size"] == 10
    item = result.output["items"][0]
    assert item["resume_id"] == "res_abc"
    assert item["candidate_name"] == "张三"
    assert item["skills"] == ["Python", "React"]
    assert item["candidate_status"] == "NEW"
    assert item["created_at"] == "2026-07-20T12:00:00"


# ---------------------------------------------------------------------------
# TC-S5-04-4
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc_s5_04_4_read_jd_not_found_and_success():
    """read_jd 不存在 jd_id → ToolParamError；存在 → 返回 JD dict。"""
    router = ToolRouter(registry=SkillRegistry())

    class _MissingJDService:
        def __init__(self, db):
            self.db = db

        async def get_jd(self, jd_id: str):
            return None

    class _FoundJDService:
        def __init__(self, db):
            self.db = db

        async def get_jd(self, jd_id: str):
            class _JD:
                def __init__(self):
                    self.jd_id = jd_id
                    self.title = "后端工程师"
                    self._sa_instance_state = object()  # 模拟 SQLAlchemy 内部状态

            return _JD()

    import app.agent.orchestrator.tool_router as tr_module

    # 不存在 → ToolParamError
    orig = tr_module.JDService
    tr_module.JDService = _MissingJDService
    try:
        with pytest.raises(ToolParamError) as exc:
            await router.dispatch("read_jd", {"jd_id": "jd_notexist"}, db=object())
        assert "jd_notexist" in exc.value.message
    finally:
        tr_module.JDService = orig

    # 存在 → 返回 dict（剔除 _sa_instance_state）
    tr_module.JDService = _FoundJDService
    try:
        result = await router.dispatch("read_jd", {"jd_id": "jd_123"}, db=object())
    finally:
        tr_module.JDService = orig

    assert result.success is True
    assert result.output["jd_id"] == "jd_123"
    assert result.output["title"] == "后端工程师"
    assert "_sa_instance_state" not in result.output


# ---------------------------------------------------------------------------
# TC-S5-04-5
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc_s5_04_5_dispatch_internal_skill_refused():
    """dispatch 命中 internal Skill → SkillNotDispatchableError，不执行。"""
    reg = SkillRegistry()
    reg.register_skill(_InternalStub())
    router = ToolRouter(registry=reg)

    with pytest.raises(SkillNotDispatchableError) as exc:
        await router.dispatch("stub-internal", {})
    assert exc.value.tool_name == "stub-internal"


# ---------------------------------------------------------------------------
# TC-S5-04-6
# ---------------------------------------------------------------------------
def test_tc_s5_04_6_route_task_type_extract_and_default():
    """route_task_type 提取 task_type；缺失/None/空 → 'unknown'。"""
    assert route_task_type({"task_type": "match"}) == "match"
    assert route_task_type({"task_type": "jd_generation"}) == "jd_generation"
    assert route_task_type({}) == "unknown"
    assert route_task_type({"task_type": None}) == "unknown"
    assert route_task_type({"task_type": ""}) == "unknown"


# ---------------------------------------------------------------------------
# TC-PR17-5（PR-17 · 阶段 2 转绿）· registry task_type 冲突检测
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="PR-17 registry task_type→tool_name conflict detection not yet implemented", strict=False)
async def test_registry_task_type_conflict_raises(tmp_path):
    """两个非 internal skill 声明相同 task_type → SkillRegistry 初始化 raise ValueError。"""
    conflict_dir = tmp_path / "conflict_skills"
    for sid, name in (("skill-a", "Skill A"), ("skill-b", "Skill B")):
        ver_dir = conflict_dir / sid / "v1_0_0"
        ver_dir.mkdir(parents=True)
        (ver_dir / "skill.yaml").write_text(
            f"skill_id: {sid}\n"
            f"skill_name: {name}\n"
            f'version: "1.0.0"\n'
            f"internal: false\n"
            f"task_type: profile_candidate\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError) as exc:
        SkillRegistry(skills_dir=conflict_dir)
    assert "conflict" in str(exc.value)
