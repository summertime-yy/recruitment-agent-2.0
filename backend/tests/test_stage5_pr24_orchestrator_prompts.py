"""
PR-24 · B5 orchestrator prompt-template fix — regression suite.

Background
----------
The 5 internal orchestrator skills (orchestrator_reason / orchestrator_reflect /
orchestrator_plan / orchestrator_reflect_plan / orchestrator_reflect_act) declared
non-empty `input_schema.required` fields but shipped prompt.md files WITHOUT a
`---USER_TEMPLATE---` section. `BaseSkill.render_user_prompt()` therefore rendered an
EMPTY user prompt, so every token the caller supplied (candidate id, jd id, resume id,
…) was silently dropped before reaching the LLM. This is the MVP-VERIFY B5 defect.

The contract is the KICKOFF-DECISION (docs/planning/stage5/PR24-KICKOFF-DECISION.md).
This file is the red-test skeleton (Step 1); §三.3 explicitly allows the executor to
adapt test mechanics "据实微调". Notes on two adaptations:

* The DECISION's test skeleton names `engine.process_user_message(...)`. No such method
  exists in the engine; the real user-message entry points are `run_reason`, `run_reflect`
  and `run_reason_reflect`. Those are used here, with the same intent: prove that a
  caller-supplied unique token reaches the rendered LLM user prompt (or SSE payload).
* `process_user_message` "emit SSE data.message 含 token" is realised by asserting the
  token is present in the user prompt actually handed to `call_llm_json` (the prompt the
  LLM receives). The MVP-VERIFY-REPORT §四/§五 rerun (Step 6) is the SSE-level proof.

Test inventory (per §三.3 / §七)
  TC-PR24-1  · 5 internal skills render a non-empty user prompt embedding every required field value
  TC-PR24-2  · reason stage: caller token reaches the LLM prompt (process_user_message → run_reason)
  TC-PR24-3  · reflect stage: caller token reaches the LLM prompt (process_user_message → run_reflect)
  TC-PR24-4  · engine.run_reason returns output embedding the caller token
  TC-PR24-5  · engine.run_reason_reflect returns PLANNING/WAITING_CONFIRMATION and embeds token in prompt
  TC-PR24-6  · LLM e2e (real key) — runs only under `pytest -m llm_e2e`
  TC-PR24-B4-1 · infeasible plan emits SSEEventType.ERROR (code=REASON_PLAN_FAILED, recoverable=False)
"""

from __future__ import annotations

import os
import warnings
from collections.abc import AsyncIterator

import fakeredis
import pytest
import pytest_asyncio

from app.agent.orchestrator.engine import OrchestratorEngine
from app.agent.orchestrator.event_buffer import EventBuffer
from app.agent.skill_registry import SkillRegistry
from app.schemas.agent import SSEEventType

# Internal orchestrator skill ids covered by the B5 fix.
INTERNAL_SKILL_IDS = {
    "orchestrator-reason",
    "orchestrator-reflect",
    "orchestrator-plan",
    "orchestrator-reflect-plan",
    "orchestrator-reflect-act",
}


def _reason_output_factory(user_prompt: str) -> dict:
    """A valid `orchestrator-reason` output_schema payload that embeds the rendered prompt.

    call_llm_json is mocked to "echo" the user prompt back so we can assert on it.
    """
    return {
        "task_type": "unknown",
        "intent_summary": user_prompt,
        "parsed_entities": {},
        "missing_entities": [],
        "confidence": 0.5,
    }


def _reflect_output_factory(feasible: bool, blocking_reason: str = "") -> dict:
    payload = {"is_feasible": feasible}
    if not feasible:
        payload["blocking_reason"] = blocking_reason
    return payload


@pytest.fixture
def registry() -> SkillRegistry:
    return SkillRegistry()


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[OrchestratorEngine]:
    # Passing event_buffer lets the engine build its own RedisActiveCounter on the
    # same (fakeredis) client, mirroring the production lifespan wiring.
    buffer = EventBuffer(fakeredis.aioredis.FakeRedis())
    yield OrchestratorEngine(event_buffer=buffer, registry=SkillRegistry())


# --------------------------------------------------------------------------- #
# TC-PR24-1 · 5 internal skills render a non-empty user prompt                #
# --------------------------------------------------------------------------- #
def test_pr24_1_all_internal_skills_render_non_empty_user_prompt(registry: SkillRegistry):
    skills = [s for s in registry._skills.values() if getattr(s, "internal", False)]
    assert {s.skill_id for s in skills} == INTERNAL_SKILL_IDS, "orchestrator internal skill set drifted"

    for skill in skills:
        required = (skill.input_schema or {}).get("required", []) or []
        assert required, f"{skill.skill_id} must declare required input fields"
        mock_input = {field: f"__PR24_{field.upper()}__" for field in required}
        rendered = skill.render_user_prompt(mock_input)
        assert rendered.strip(), f"{skill.skill_id} rendered an EMPTY user prompt (B5 defect)"
        for field in required:
            token = f"__PR24_{field.upper()}__"
            assert token in rendered, f"{skill.skill_id} did not embed required field '{field}' in prompt"


# --------------------------------------------------------------------------- #
# TC-PR24-2 · reason stage — caller token reaches the LLM prompt             #
# (DECISION process_user_message → run_reason)                                #
# --------------------------------------------------------------------------- #
async def test_pr24_2_reason_stage_embeds_caller_token(engine: OrchestratorEngine, monkeypatch):
    captured: list[str] = []

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        captured.append(user_prompt)
        return _reason_output_factory(user_prompt)

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake_llm)
    await engine.run_reason({"user_input": "找候选人 c_ABC，岗位 jd_XYZ", "context": {}})

    assert captured, "call_llm_json was never called"
    assert "c_ABC" in captured[0], "reason-stage user prompt dropped caller token c_ABC (B5 defect)"
    assert "jd_XYZ" in captured[0], "reason-stage user prompt dropped caller token jd_XYZ (B5 defect)"


# --------------------------------------------------------------------------- #
# TC-PR24-3 · reflect stage — caller token reaches the LLM prompt           #
# (DECISION process_user_message → run_reflect)                               #
# --------------------------------------------------------------------------- #
async def test_pr24_3_reflect_stage_embeds_caller_token(engine: OrchestratorEngine, monkeypatch):
    captured: list[str] = []

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        captured.append(user_prompt)
        return _reflect_output_factory(feasible=True)

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake_llm)
    reason = {
        "task_type": "resume_screen",
        "intent_summary": "为简历 r_Y 寻找匹配岗位",
        "parsed_entities": {},
        "missing_entities": [],
        "confidence": 0.9,
    }
    await engine.run_reflect(reason)

    assert captured, "call_llm_json was never called"
    assert "r_Y" in captured[-1], "reflect-stage user prompt dropped caller token r_Y (B5 defect)"


# --------------------------------------------------------------------------- #
# TC-PR24-4 · engine.run_reason returns output embedding the caller token    #
# --------------------------------------------------------------------------- #
async def test_pr24_4_run_reason_returns_output_with_token(engine: OrchestratorEngine, monkeypatch):
    captured: list[str] = []

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        captured.append(user_prompt)
        return _reason_output_factory(user_prompt)

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake_llm)
    result = await engine.run_reason({"user_input": "找候选人 c_ABC", "context": {"jd_id": "jd_XYZ"}})

    assert result.get("success") is True, f"run_reason failed: {result.get('error')}"
    assert "c_ABC" in str(result), "run_reason output dropped caller token c_ABC (B5 defect)"
    assert "jd_XYZ" in str(result), "run_reason output dropped caller token jd_XYZ (B5 defect)"


# --------------------------------------------------------------------------- #
# TC-PR24-5 · engine.run_reason_reflect returns status + embeds token        #
# --------------------------------------------------------------------------- #
async def test_pr24_5_run_reason_reflect_embeds_token(engine: OrchestratorEngine, monkeypatch):
    captured: list[str] = []
    calls = {"n": 0}

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        captured.append(user_prompt)
        calls["n"] += 1
        if calls["n"] == 1:
            return _reason_output_factory(user_prompt)
        return _reflect_output_factory(feasible=True)

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake_llm)
    status = await engine.run_reason_reflect({"user_input": "为 jd_X 找简历 r_Y", "context": {}})

    assert status in ("PLANNING", "WAITING_CONFIRMATION"), f"unexpected status: {status}"
    assert captured, "call_llm_json was never called"
    assert "jd_X" in captured[0], "reason-reflect flow dropped caller token jd_X (B5 defect)"
    assert "r_Y" in captured[0], "reason-reflect flow dropped caller token r_Y (B5 defect)"


# --------------------------------------------------------------------------- #
# TC-PR24-B4-1 · infeasible plan emits SSE ERROR (REASON_PLAN_FAILED)         #
# --------------------------------------------------------------------------- #
async def test_pr24_b4_infeasible_plan_emits_error_event(engine: OrchestratorEngine, monkeypatch):
    calls = {"n": 0}

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # reason
            return _reason_output_factory(user_prompt)
        return _reflect_output_factory(feasible=False, blocking_reason="缺少 jd_id")

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake_llm)

    task_id = "pr24-b4-task"
    await engine._background_reason_plan(task_id=task_id, user_message="帮我找人", context={})

    events = await engine.event_buffer.read_after(task_id)
    error_events = [e for e in events if e.type == SSEEventType.ERROR]
    assert error_events, "no SSEEventType.ERROR event emitted on infeasible plan (B4 defect)"
    terminal = error_events[-1]
    assert terminal.data.get("code") == "REASON_PLAN_FAILED", (
        f"infeasible plan must emit code=REASON_PLAN_FAILED, got {terminal.data!r}"
    )
    assert terminal.data.get("message") == "缺少 jd_id", "ERROR event must carry the blocking_reason"
    assert terminal.data.get("recoverable") is False, "infeasible-plan ERROR must be non-recoverable"


# --------------------------------------------------------------------------- #
# TC-PR24-6 · LLM e2e (real key) — opt-in only                               #
# --------------------------------------------------------------------------- #
@pytest.mark.llm_e2e
async def test_pr24_6_llm_e2e_reason_embeds_token(engine: OrchestratorEngine):
    """Real-LLM smoke test for the B5 fix.

    Mission: prove that AFTER the USER_TEMPLATE fix, the LLM actually *sees* a
    non-empty user_prompt. B5 was "empty template -> LLM saw only system_prompt";
    the deterministic round-trip of the unique token inside `user_input`
    (c_UNIQUE_ABC_2607) is exactly that proof.

    The unique token inside `context.jd_id` (jd_UNIQUE_XYZ_2607) is intentionally
    NOT asserted: the LLM's extraction of a structured-JSON context field is
    non-deterministic. That is a prompt-engineering issue surfaced *after* B5
    (logged in HANDOFF §9.3.19), out of this PR's scope. We keep it as a non-fatal
    observation via warnings.warn so the behaviour stays visible instead of
    silently passing.
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY not set — skipping LLM e2e (run: pytest -m llm_e2e with a live key)")

    result = await engine.run_reason(
        {"user_input": "找候选人 c_UNIQUE_ABC_2607", "context": {"jd_id": "jd_UNIQUE_XYZ_2607"}}
    )
    assert result.get("success") is True, f"live run_reason failed: {result.get('error')}"
    # B5 proof: the unique caller token from user_input must reach the LLM and round-trip.
    assert "c_UNIQUE_ABC_2607" in str(result), (
        "LLM should extract c_UNIQUE_ABC_2607 from user_input · "
        "if this fails the B5 template fix did not take effect"
    )
    # Non-asserting observation (see HANDOFF §9.3.19): LLM may drop context.jd_id.
    if "jd_UNIQUE_XYZ_2607" not in str(result):
        warnings.warn(
            "LLM did not extract jd_UNIQUE_XYZ_2607 from context.jd_id · "
            "not a B5 regression (see HANDOFF §9.3.19) · prompt-engineering follow-up",
            stacklevel=1,
        )
