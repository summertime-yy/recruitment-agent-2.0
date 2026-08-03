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
    db_session: Any,
) -> None:
    """S3.3 boundary 3 red-test: when run_execute is invoked WITH a
    session_factory, the engine must open a session and forward a real
    AsyncSession (not None) into tool_router.dispatch.

    Before commit 2, the run_execute signature did not accept
    session_factory so the call site could not even pass it; the engine
    fell into the `else` branch of _background_execute and dispatch saw
    db=None. After commit 2, session_factory wires through and dispatch
    receives a real session.
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

    def _session_factory():
        # Reuse the test fixture session; engine is expected to enter the
        # `if session_factory is not None` branch and call this.
        return _AsyncSessionCM(db_session)

    await eng.run_execute("task_pr28_hydrate", plan=plan, session_factory=_session_factory)
    # Allow the background coroutine to flush.
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-execute-")]
    await asyncio.gather(*bg, return_exceptions=True)
    assert recorded.get("db_is_none") is False, (
        "engine.run_execute did not propagate a real db into the tool "
        "router (PR-21 leak: db=None -> hydration silently returns {})"
    )


class _AsyncSessionCM:
    """Async context manager shim so the engine's `async with session_factory()`
    call can wrap a pre-existing AsyncSession (the conftest fixture already
    manages transaction lifecycle).
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # No-op: the conftest fixture rolls back at teardown.
        return None


# ===========================================================================
# S5.1  attribution-verification test: post-commit-2, hydrate_tool_input
#       must run with a real db and pull parsed_content / existing_tags
#       from the seeded Resume row.  This is the direct behavioural
#       evidence that the §2.2 inference (db=None -> silent {}) has been
#       closed by the session_factory pass-through.
# ===========================================================================
async def test_pr28_hydration_receives_real_db_and_pulls_parsed_content(
    db_session: Any,
) -> None:
    """S5.1 boundary 1 attribution test.

    Sequence:
      1. Seed a Resume with non-null parsed_content and known tags.
      2. Build a tool_router that delegates to candidate-profile hydration
         (mirrors the production dispatch -> hydrate path).
      3. Invoke dispatch with a candidate_id-only tool_input and the real
         session as `db`.
      4. Assert the dispatched tool_input contains parsed_content +
         existing_tags pulled from the seeded row.

    Before commit 2 the run_execute path's db was None, so step 3 would
    raise `ToolParamError("hydration for 'candidate-profile' requires a
    db session")` (PR-26 S3.3 already hardens this). After commit 2 the
    session_factory flows through and step 4 succeeds.
    """
    from factories import build_resume

    from app.agent.orchestrator.tool_router import ToolRouter

    # 1. seed (factory supplies the NOT-NULL columns file_type/file_size/...)
    resume = build_resume(
        resume_id="res_pr28_hydrate_xxx",
        parsed_content={"summary": "attribution-fixture"},
        tags=["技术", "高潜"],
    )
    db_session.add(resume)
    await db_session.flush()

    # 2. build a router that runs real hydration + a recording skill
    from app.agent.base_skill import SkillResult
    from app.agent.orchestrator.hydration import HYDRATION_RULES

    received_input: dict = {}

    class _RecordingSkill:
        internal = False
        input_schema = None  # commit 3 注入；这里不依赖

        async def execute(self, tool_input):
            received_input.update(tool_input)
            return SkillResult(
                success=True,
                output={"profile_tags": [], "summary": "", "strengths": [], "risks": []},
            )

    class _Reg:
        def __init__(self) -> None:
            self.skills = {"candidate-profile": _RecordingSkill()}

        def get_skill(self, tool_name: str):
            if tool_name in self.skills:
                return self.skills[tool_name]
            raise KeyError(tool_name)

    router = ToolRouter(registry=_Reg())  # type: ignore[arg-type]

    # 3. invoke dispatch with real session as db (mirrors what
    #    engine.run_execute does post-commit-2)
    tool_input_after_hydrate = await HYDRATION_RULES["candidate-profile"](
        {"candidate_id": "res_pr28_hydrate_xxx"}, db_session
    )
    await router.dispatch(
        "candidate-profile",
        tool_input_after_hydrate,
        db=db_session,
    )

    # 4. assert
    assert received_input.get("parsed_content") == {"summary": "attribution-fixture"}, (
        f"expected parsed_content from seeded Resume, got {received_input!r}"
    )
    assert list(received_input.get("existing_tags") or []) == ["技术", "高潜"], (
        f"expected tags from seeded Resume, got {received_input!r}"
    )
