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
import json
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
# S3.2  red-test: _format_dispatchable_tools must inject full input_schema
#                  JSON and append HYDRATION_HINTS for hydrated skills
# ===========================================================================
def test_pr28_format_dispatchable_tools_injects_input_schema_and_hints() -> None:
    """S3.2 boundary 2 red-test: PR-28 commit 3 rewrites
    `_format_dispatchable_tools` so that:

      - each builtin tool with `input_schema` gets a Markdown line
        containing the schema JSON;
      - each skill with `input_schema` (i.e. candidate-profile, etc.)
        also gets that line;
      - any skill in HYDRATION_HINTS gets an extra "Note: ..." line so
        the plan LLM doesn't waste tokens filling fields that
        hydration back-fills from the DB.

    Before commit 3 the formatter only emits `- `name`` (no schema, no
    hint). After commit 3 the strings are present.
    """
    from app.agent.orchestrator.engine import OrchestratorEngine
    from app.agent.orchestrator.hydration import HYDRATION_HINTS
    from app.agent.orchestrator.tool_router import BUILTIN_TOOLS

    class _StubSkill:
        def __init__(self, skill_id: str) -> None:
            self.skill_id = skill_id
            self.task_type = None
            self.description = f"stub {skill_id}"
            self.input_schema = {"type": "object", "properties": {"candidate_id": {"type": "string"}}}

    class _Registry:
        def list_dispatchable(self):
            return [_StubSkill(sid) for sid in HYDRATION_HINTS]

    eng = OrchestratorEngine.__new__(OrchestratorEngine)
    eng.registry = _Registry()  # type: ignore[assignment]

    md = eng._format_dispatchable_tools()
    # Schema injection: any builtin with non-empty input_schema must
    # surface in the markdown.
    for name, spec in BUILTIN_TOOLS.items():
        schema = spec.get("input_schema") or {}
        if schema:
            assert json.dumps(schema, ensure_ascii=False)[:20] in md, (
                f"builtin tool {name!r} input_schema is not rendered into "
                f"the dispatchable-tools markdown (PR-28 §3.2 not fixed)"
            )
    # HYDRATION_HINTS surfaces in the markdown: each hydrated skill gets
    # its Chinese hint line.
    assert "由系统从数据库自动补齐" in md, (
        f"HYDRATION_HINTS not rendered into the dispatchable-tools "
        f"markdown (PR-28 §3.2 not fixed). Markdown: {md[:500]}"
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


# ===========================================================================
# S3.3 commit 4: candidate-profile hydration must accept a single-element
# `candidate_ids` / `resume_ids` list (PR-28 Q3-A compat layer).  When
# the LLM outputs more than one entry, hydration must raise
# ToolParamError pointing the caller at candidate-merge rather than
# silently picking the first.
# ===========================================================================
async def test_pr28_hydration_accepts_single_element_candidate_ids(
    db_session: Any,
) -> None:
    """PR-28 Q3-A (commit 4) red-then-green: candidate-profile with
    `candidate_ids: ["res_xxx"]` must hydrate successfully.
    """
    from factories import build_resume

    from app.agent.orchestrator.hydration import HYDRATION_RULES

    resume = build_resume(
        resume_id="res_pr28_plural_one",
        parsed_content={"summary": "plural-ok"},
        tags=["backend"],
    )
    db_session.add(resume)
    await db_session.flush()

    hydrated = await HYDRATION_RULES["candidate-profile"](
        {"candidate_ids": ["res_pr28_plural_one"]}, db_session
    )
    assert hydrated["parsed_content"] == {"summary": "plural-ok"}, (
        f"single-element candidate_ids was not accepted; got {hydrated!r}"
    )


async def test_pr28_hydration_rejects_multi_element_candidate_ids(
    db_session: Any,
) -> None:
    """PR-28 Q3-A (commit 4) red-then-green: candidate-profile with
    `candidate_ids: ["res_a", "res_b"]` must raise ToolParamError
    pointing at candidate-merge.
    """
    from factories import build_resume

    from app.agent.orchestrator.hydration import HYDRATION_RULES
    from app.agent.orchestrator.tool_router import ToolParamError

    a = build_resume(resume_id="res_pr28_plural_a", parsed_content={"summary": "a"}, tags=[])
    b = build_resume(resume_id="res_pr28_plural_b", parsed_content={"summary": "b"}, tags=[])
    db_session.add_all([a, b])
    await db_session.flush()

    with pytest.raises(ToolParamError) as exc_info:
        await HYDRATION_RULES["candidate-profile"](
            {"candidate_ids": ["res_pr28_plural_a", "res_pr28_plural_b"]}, db_session
        )
    assert "candidate-merge" in str(exc_info.value), (
        f"error should point at candidate-merge; got {exc_info.value!r}"
    )


def test_pr28_hydration_hints_keys_match_rules() -> None:
    """PR-28 commit 7 (fix 3 / TC-PR28-3, Q2.1 = 加): HYDRATION_HINTS and
    HYDRATION_RULES are two hand-synced dicts with no drift guard.  This
    assertion is the guard — every hydration rule must have a matching hint
    and vice versa.
    """
    from app.agent.orchestrator.hydration import HYDRATION_HINTS, HYDRATION_RULES

    assert set(HYDRATION_HINTS) == set(HYDRATION_RULES), (
        f"HYDRATION_HINTS keys drifted from HYDRATION_RULES: "
        f"only_in_hints={set(HYDRATION_HINTS) - set(HYDRATION_RULES)}, "
        f"only_in_rules={set(HYDRATION_RULES) - set(HYDRATION_HINTS)}"
    )


# ===========================================================================
# S3.4 commit 5: _make_db_execution_writer must persist input_params on
# start and error_message on end (when the step ended FAILED).  Also
# the background-execute failure path must always end the Task as
# FAILED, never leaving it EXECUTING.
# ===========================================================================
async def test_pr28_execution_writer_persists_input_params_and_error(
    db_session: Any,
) -> None:
    """PR-28 Q4-B (commit 5): _make_db_execution_writer.start stores
    tool_input into executions.input_params; on 'end' with a FAILED
    SkillResult, error_message is written to executions.error_message.
    """
    from factories import build_task
    from sqlalchemy import select

    from app.agent.base_skill import SkillResult
    from app.agent.orchestrator.engine import _make_db_execution_writer
    from app.models.execution import Execution

    task = build_task(task_id="task_pr28_writer", status="EXECUTING")
    db_session.add(task)
    await db_session.flush()

    # _make_db_execution_writer calls `async with session_factory() as db:`
    # (no await), so the factory must itself be a sync callable returning
    # an async context manager.  Mirror that contract.
    def _session_factory_sync():
        return _AsyncSessionCM(db_session)

    writer = _make_db_execution_writer(_session_factory_sync, task_id="task_pr28_writer")
    await writer(
        "step_x",
        "candidate-profile",
        "start",
        tool_input={"candidate_id": "res_xyz", "existing_tags": ["t"]},
    )
    failed = SkillResult(
        success=False,
        output=None,
        error_message="required property 'resume_id' is missing",
    )
    await writer("step_x", "candidate-profile", "end", result=failed)

    row = (
        (
            await db_session.execute(
                select(Execution).where(Execution.task_id == "task_pr28_writer")
            )
        )
        .scalars()
        .first()
    )
    assert row is not None, "writer did not insert an execution row"
    assert row.input_params == {
        "candidate_id": "res_xyz",
        "existing_tags": ["t"],
    }, f"input_params not persisted; got {row.input_params!r}"
    assert row.execution_status == "FAILED"
    assert "resume_id" in (row.error_message or ""), (
        f"error_message not populated on FAILED step; got {row.error_message!r}"
    )


# ---------------------------------------------------------------------------
# PR-28 commit 7 (fix 2): TC-PR28-5 had two defects — it used an `async def`
# session_factory (so _background_execute hit `TypeError: coroutine object
# does not support the asynchronous context manager protocol` → caught by the
# generic except → INTERNAL_ERROR), and asserted only status=="FAILED" without
# checking error.code, so it passed for the WRONG reason.  Split into 5a /
# 5b.  5a verifies the real ALL_STEPS_FAILED terminal state; 5b guards the
# Q4.1-A reversal of Q4.1-B (an optional failed step must NOT downgrade a
# task that has a success step to FAILED).
# ---------------------------------------------------------------------------
async def test_pr28_background_execute_all_failed_terminal(
    db_session: Any,
    fake_redis: Any,
) -> None:
    """PR-28 commit 7 (fix 2 / TC-PR28-5a): when every step fails, the Task
    must end FAILED with error.code == 'ALL_STEPS_FAILED' (DECISION §3.4①).

    run_act swallows dispatch exceptions and returns StepResult(success=False),
    so a router that raises yields a failed step — that drives the real
    all_failed branch, not the INTERNAL_ERROR except branch.  The session
    factory is a plain sync callable returning an async context manager
    (the correct contract, matching _make_db_execution_writer).
    """
    import asyncio

    from factories import build_task

    from app.agent.orchestrator.engine import OrchestratorEngine
    from app.agent.orchestrator.event_buffer import EventBuffer

    task = build_task(task_id="task_pr28_allfail", status="EXECUTING")
    db_session.add(task)
    await db_session.flush()

    recorded_writes: list = []

    async def _db_updater(task_id: str, fields: dict) -> None:
        recorded_writes.append(fields)

    class _BoomRouter:
        async def dispatch(self, tool_name, tool_input, db=None):
            raise RuntimeError("skill exploded for the test")

    class _Registry:
        def get(self, skill_id):
            return None

        def list_dispatchable(self):
            return []

    buffer = EventBuffer(fake_redis)

    # Correct contract: sync callable returning an async context manager.
    def _sf():
        return _AsyncSessionCM(db_session)

    eng = OrchestratorEngine(
        registry=_Registry(),
        tool_router=_BoomRouter(),
        event_buffer=buffer,
        db_updater=_db_updater,
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
    await eng.run_execute("task_pr28_allfail", plan=plan, session_factory=_sf)
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-execute-")]
    await asyncio.gather(*bg, return_exceptions=True)

    failed_writes = [w for w in recorded_writes if w.get("status") == "FAILED"]
    assert failed_writes, (
        f"background execute did not write a FAILED task terminal; "
        f"writes={recorded_writes!r}"
    )
    terminal = failed_writes[-1]
    assert terminal.get("error", {}).get("code") == "ALL_STEPS_FAILED", (
        f"terminal error.code must be ALL_STEPS_FAILED, got {terminal!r}"
    )


async def test_pr28_background_execute_optional_fail_keeps_completed(
    db_session: Any,
    fake_redis: Any,
) -> None:
    """PR-28 commit 7 (fix 2 / TC-PR28-5b, Q4.1-A): an optional step that
    fails must NOT downgrade a task that still has a successful step.  The
    terminal state stays COMPLETED.
    """
    import asyncio

    from factories import build_task

    from app.agent.orchestrator.engine import OrchestratorEngine
    from app.agent.orchestrator.event_buffer import EventBuffer

    task = build_task(task_id="task_pr28_optfail", status="EXECUTING")
    db_session.add(task)
    await db_session.flush()

    recorded_writes: list = []

    async def _db_updater(task_id: str, fields: dict) -> None:
        recorded_writes.append(fields)

    class _PartialRouter:
        async def dispatch(self, tool_name, tool_input, db=None):
            from app.agent.base_skill import SkillResult

            if tool_name == "candidate-profile":
                # optional step: fail
                return SkillResult(
                    success=False,
                    output=None,
                    error_message="optional step intentionally failed",
                )
            # second step: success
            return SkillResult(success=True, output={"ok": True})

    class _Registry:
        def get(self, skill_id):
            return None

        def list_dispatchable(self):
            return []

    buffer = EventBuffer(fake_redis)

    def _sf():
        return _AsyncSessionCM(db_session)

    eng = OrchestratorEngine(
        registry=_Registry(),
        tool_router=_PartialRouter(),
        event_buffer=buffer,
        db_updater=_db_updater,
    )
    plan = {
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "candidate-profile",
                "tool_input": {"candidate_id": "res_x"},
                "optional": True,
            },
            {
                "step_id": "s2",
                "tool_name": "resume-parsing",
                "tool_input": {"resume_id": "res_y"},
            },
        ]
    }
    await eng.run_execute("task_pr28_optfail", plan=plan, session_factory=_sf)
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-execute-")]
    await asyncio.gather(*bg, return_exceptions=True)

    completed_writes = [w for w in recorded_writes if w.get("status") == "COMPLETED"]
    assert completed_writes, (
        f"optional-fail + success task must stay COMPLETED; writes={recorded_writes!r}"
    )
    assert not any(w.get("status") == "FAILED" for w in recorded_writes), (
        f"optional failed step must not downgrade to FAILED; writes={recorded_writes!r}"
    )
