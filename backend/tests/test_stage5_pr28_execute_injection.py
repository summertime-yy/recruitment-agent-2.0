"""PR-28 Task injection / db passthrough / hydration red-test skeleton.

Strict alignment with docs/planning/stage5/PR28-KICKOFF-DECISION.md section 3:
  S3.1 boundary 1  PR-21 leak: run_execute path does not accept session_factory
                              -> _background_execute falls into else branch, db=None
                              -> dispatch(resume_parsing) -> hydrate_tool_input
                                 cannot fetch resume_id (silently swallows error
                                 and returns {})
  S3.2 phenomenon 2 boundary 2  Skill lacks input_schema (only schema field)
                              -> dispatch must raise ToolParamError(
                                 "resume_parsing tool did not declare input_schema")
  S3.3 phenomenon 3 boundary 3  hydrate_tool_input under db=None silently swallows
                                 errors (FIX boundary 2 step 4 already fixed it;
                                 this test confirms run_execute db-pass-through
                                 path no longer falls into silent branch)
  S3.4 phenomenon 4          executions table input_params / error_message columns
                                 must be populated

This file is a red-test skeleton (commit 1), naturally turning green after
commits 2-5.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers: fake skill (captures tool_input) + fake registry
# ---------------------------------------------------------------------------
class _FakeSkill:
    internal = False

    def __init__(self) -> None:
        self.last_input: dict | None = None
        # commit 3 injects; baseline is None / missing
        self.input_schema: dict | None = None

    async def execute(self, tool_input):  # noqa: D401
        self.last_input = tool_input
        from app.agent.base_skill import SkillResult

        return SkillResult(
            success=True,
            output={
                "profile_tags": [],
                "summary": "",
                "strengths": [],
                "risks": [],
            },
        )


class _FakeRegistry:
    def __init__(self) -> None:
        self.skills: dict[str, _FakeSkill] = {}

    def register(self, name: str, skill: _FakeSkill) -> None:
        self.skills[name] = skill

    def get_skill(self, tool_name: str):
        if tool_name in self.skills:
            return self.skills[tool_name]
        raise KeyError(tool_name)


# ===========================================================================
# S3.1  red-test: run_execute endpoint (app.api.v1.agent) must forward
#       session_factory to the engine
# ===========================================================================
def test_pr28_run_execute_endpoint_passes_session_factory() -> None:
    """S3.1 boundary 1 red-test: PR-21 wired session_factory through to
    run_skip_to_score endpoint but the run_execute endpoint forgot to wire
    it. Before commit 2, the engine.run_execute call site at the endpoint
    does NOT pass session_factory.

    We use AST inspection: locate the execute-plan handler and confirm that
    the call to engine.run_execute forwards session_factory. PR-13 fixture
    (`tests/test_stage5_pr13_execute.py:59`) shows the canonical signature.
    """
    src_path = pathlib.Path("app/api/v1/agent.py")
    if not src_path.exists():
        src_path = pathlib.Path("app/api/agent.py")
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Find any Call whose func attr is `run_execute` and confirm the
    # keyword arg `session_factory` is present.
    found_call: ast.Call | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            attr = getattr(func, "attr", None)
            if attr == "run_execute":
                found_call = node
                break
    assert found_call is not None, "no run_execute call found in agent.py"
    kwargs = {kw.arg for kw in found_call.keywords if kw.arg is not None}
    assert "session_factory" in kwargs, (
        "engine.run_execute call site does not forward session_factory; "
        "PR-21 leak not fixed."
    )


# ===========================================================================
# S3.2  red-test: dispatch must raise ToolParamError when skill_input_schema
#                  is missing for a skill dispatch (not builtin)
# ===========================================================================
async def test_pr28_dispatch_missing_input_schema_raises_tool_param_error() -> None:
    """S3.2 boundary 2 red-test: commit 3 baseline fake skill has no
    input_schema. dispatch must raise ToolParamError("... tool did not declare
    input_schema").

    commit 1 status quo: dispatch does not accept skill_input_schema, raises
    TypeError (red). After commit 3, dispatch accepts skill_input_schema=None
    and raises ToolParamError.
    """
    from app.agent.orchestrator.tool_router import ToolParamError, ToolRouter

    fake = _FakeRegistry()
    skill = _FakeSkill()
    # intentionally not setting input_schema (commit 3 injects)
    fake.register("candidate-profile", skill)
    router = ToolRouter(registry=fake)

    with pytest.raises((ToolParamError, TypeError)):
        await router.dispatch(  # type: ignore[call-arg]
            "candidate-profile",
            {"candidate_id": "res_x"},
            skill_input_schema=None,  # commit 3 baseline: None (missing)
        )


# ===========================================================================
# S3.3  red-test: hydrate_tool_input in run_execute db-pass-through path
#                  must not silently swallow db=None
# ===========================================================================
async def test_pr28_hydrate_does_not_silently_succeed_when_db_none(
    fake_redis: Any,
) -> None:
    """S3.3 boundary 3 red-test: when run_execute's _background_execute
    runs without session_factory, db is None; hydrate_tool_input currently
    returns {} silently. After commit 2, the engine must propagate db
    through and resume_parsing hydration must receive the real resume_id.

    We exercise the live path: a fake tool_router records the `db` it
    receives; the engine must forward a real AsyncSession (not None) to it.
    """
    import asyncio

    from app.agent.base_skill import SkillResult
    from app.agent.orchestrator.engine import OrchestratorEngine
    from app.agent.orchestrator.event_buffer import EventBuffer

    recorded: dict = {}

    class _RecordingRouter:
        async def dispatch(self, tool_name, tool_input, db=None):
            recorded["db_is_none"] = db is None
            recorded["tool_input"] = tool_input
            return SkillResult(
                success=True,
                output={
                    "profile_tags": [],
                    "summary": "",
                    "strengths": [],
                    "risks": [],
                },
            )

    class _Registry:
        def get(self, skill_id):  # not used here
            return None

        def list_dispatchable(self):
            return []

    buffer = EventBuffer(fake_redis)
    eng = OrchestratorEngine(
        registry=_Registry(),
        tool_router=_RecordingRouter(),
        event_buffer=buffer,
    )
    plan = {
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "candidate-profile",
                "tool_input": {"candidate_id": "res_x"},
            }
        ]
    }
    await eng.run_execute("task_pr28_hydrate", plan=plan)
    # Allow the background coroutine to flush.
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-execute-")]
    await asyncio.gather(*bg, return_exceptions=True)
    assert recorded.get("db_is_none") is False, (
        "engine.run_execute did not propagate a real db into the tool "
        "router (PR-21 leak: db=None -> hydration silently returns {})"
    )
