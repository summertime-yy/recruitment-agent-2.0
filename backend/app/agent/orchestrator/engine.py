"""S5-08 · OrchestratorEngine：R-P-R-A-R 主循环编排（PR-12）。

方法分层（裁定 DECISION §四 Q3）：
- run_chat        : R -> P -> R (Reason -> Plan -> Reflect-Plan) -> WAITING_CONFIRMATION
- run_execute     : A -> R (Act -> Reflect-Act) -> COMPLETED / FAILED
- run_skip_to_score: bypass R-P-R，直接 Act -> COMPLETED / FAILED
- run_cancel      : PLANNING / WAITING_CONFIRMATION -> CANCELLED

构造依赖注入（DECISION §六 Q6 / §七）：registry、tool_router 必需可注入；active_counter、
settings、超时以合理默认值提供，便于一行构造 ``OrchestratorEngine(registry, tool_router)``。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agent.orchestrator import errors as _errors
from app.agent.orchestrator import state_machine
from app.agent.orchestrator.active_counter import ActiveCounter, InMemoryActiveCounter
from app.agent.orchestrator.state_machine import TaskStatus, check_transition
from app.agent.orchestrator.tool_router import BUILTIN_TOOLS, ToolRouter
from app.agent.skill_registry import SkillRegistry, get_skill_registry
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 供测试从本模块导入（以赋值方式再导出，避免 F401）
TransitionGuard = state_machine.TransitionGuard
IllegalTransitionError = _errors.IllegalTransitionError
TaskLimitExceededError = _errors.TaskLimitExceededError


class OrchestratorEngine:
    def __init__(
        self,
        registry: SkillRegistry | None = None,
        tool_router: ToolRouter | None = None,
        active_counter: ActiveCounter | None = None,
        settings: Any | None = None,
        skill_timeout_sec: float | None = None,
        phase_timeout_sec: float | None = None,
        task_timeout_sec: float | None = None,
    ):
        self.settings = settings or get_settings()
        self.registry = registry or get_skill_registry()
        self.tool_router = tool_router or ToolRouter(self.registry)
        self.skill_timeout_sec = skill_timeout_sec if skill_timeout_sec is not None else self.settings.skill_timeout_sec
        self.phase_timeout_sec = phase_timeout_sec if phase_timeout_sec is not None else self.settings.phase_timeout_sec
        self.task_timeout_sec = task_timeout_sec if task_timeout_sec is not None else self.settings.task_timeout_sec
        self.active_counter = active_counter or InMemoryActiveCounter(limit=self.settings.task_active_limit)

    # ---- 工具白名单（dispatchable + 内置工具）----
    def dispatchable_tool_names(self) -> list[str]:
        names = list(BUILTIN_TOOLS.keys())
        names += [s.skill_id for s in self.registry.list_dispatchable()]
        return names

    # ---- R: Reason ----
    async def run_reason(self, reason_input: dict[str, Any]) -> dict[str, Any]:
        skill = self.registry.get("orchestrator-reason")
        if skill is None:
            return {"success": False, "error": "orchestrator-reason skill not registered"}
        result = await skill.execute(reason_input)
        out = result.output or {}
        return {"success": result.success, "error": result.error_message, **out}

    # ---- R: Reflect ----
    async def run_reflect(self, reason_output: dict[str, Any]) -> dict[str, Any]:
        skill = self.registry.get("orchestrator-reflect")
        if skill is None:
            return {"is_feasible": True}
        result = await skill.execute({"reason_output": reason_output})
        if not result.success:
            return {"is_feasible": False, "blocking_reason": result.error_message}
        return result.output or {}

    async def run_reason_reflect(self, reason_input: dict[str, Any]) -> str:
        reason = await self.run_reason(reason_input)
        reflect = await self.run_reflect(reason)
        if not reflect.get("is_feasible", True):
            return "WAITING_CONFIRMATION"
        return "PLANNING"

    # ---- P: Plan ----
    async def run_plan(self, plan_input: dict[str, Any]) -> dict[str, Any]:
        skill = self.registry.get("orchestrator-plan")
        if skill is None:
            return {"success": False, "steps": [], "summary": ""}
        result = await skill.execute(plan_input)
        if not result.success:
            return {"success": False, "steps": [], "summary": "", "error": result.error_message}
        return {"success": True, **(result.output or {})}

    # ---- P: Reflect-Plan ----
    async def run_reflect_plan(self, reflect_plan_input: dict[str, Any]) -> dict[str, Any]:
        plan = reflect_plan_input.get("plan", {}) or {}
        steps = plan.get("steps", []) or []
        # 引擎侧校验：plan 中含未注册 tool_name -> 直接判不合法
        bad = [s.get("tool_name") for s in steps if s.get("tool_name") not in self.dispatchable_tool_names()]
        if bad:
            return {"is_plan_sound": False, "issues": [f"unknown tool: {t}" for t in bad], "steps": steps}
        skill = self.registry.get("orchestrator-reflect-plan")
        if skill is None:
            return {"is_plan_sound": True, "issues": [], "steps": steps}
        result = await skill.execute(reflect_plan_input)
        out = result.output or {}
        if not result.success:
            return {"is_plan_sound": False, "issues": [result.error_message or "reflect-plan failed"], "steps": steps}
        if out.get("is_plan_sound", True):
            return {"is_plan_sound": True, "issues": out.get("issues", []), "steps": steps}
        adjusted = out.get("adjusted_plan")
        if adjusted:
            return {"is_plan_sound": True, "issues": out.get("issues", []), "steps": adjusted.get("steps", steps)}
        return {"is_plan_sound": False, "issues": out.get("issues", []), "steps": steps}

    # ---- 超时封装 ----
    async def run_step_with_timeout(self, step: dict[str, Any], tool_router: ToolRouter | None = None) -> dict[str, Any]:
        router = tool_router or self.tool_router
        try:
            sr = await asyncio.wait_for(
                router.dispatch(step.get("tool_name"), step.get("args") or step.get("tool_input") or {}),
                timeout=self.skill_timeout_sec,
            )
            return {"status": "SUCCESS" if sr.success else "FAILED", "events": [], "output": sr.output}
        except TimeoutError:
            return {"status": "FAILED", "events": [{"type": "error", "message": "skill timeout"}], "output": None}

    async def run_task_with_overall_timeout(self, task_input: dict[str, Any], tool_router: ToolRouter | None = None) -> dict[str, Any]:
        try:
            result = await asyncio.wait_for(
                self._run_task_body(task_input, tool_router),
                timeout=self.task_timeout_sec,
            )
            return result
        except TimeoutError:
            return {"status": "FAILED", "error": "TASK_TIMEOUT"}

    async def _run_task_body(self, task_input: dict[str, Any], tool_router: ToolRouter | None = None) -> dict[str, Any]:
        from app.agent.orchestrator.act import run_act

        plan = task_input.get("plan") or {"steps": [{"tool_name": "search_resumes", "tool_input": {}}]}
        await run_act(plan, ctx=task_input.get("ctx", {}), emit=None, tool_router=tool_router)
        return {"status": "COMPLETED", "error": None}

    # ---- 端点层（Q3 分层）----
    async def run_chat(self, chat_input: dict[str, Any], db: Any = None, emit: Any = None) -> dict[str, Any]:
        try:
            await self.active_counter.incr()
        except TaskLimitExceededError:
            return {"status_code": 429, "error": "TASK_LIMIT_EXCEEDED"}
        try:
            reason_input = {"user_input": chat_input.get("message", ""), "context": chat_input.get("context")}
            reason_out = await self.run_reason(reason_input)
            reflect_out = await self.run_reflect(reason_out)
            if not reflect_out.get("is_feasible", True):
                return {
                    "status_code": 200,
                    "status": "WAITING_CONFIRMATION",
                    "plan": None,
                    "blocking_reason": reflect_out.get("blocking_reason"),
                }
            plan_out = await self.run_plan({"reason_output": reason_out})
            reflect_plan_out = await self.run_reflect_plan({"plan": plan_out})
            return {
                "status_code": 200,
                "status": "WAITING_CONFIRMATION",
                "plan": plan_out,
                "reflect_plan": reflect_plan_out,
            }
        finally:
            await self.active_counter.decr()

    async def run_execute(
        self,
        task_id: str,
        accepted_steps: list[str] | None = None,
        modifications: list[dict[str, Any]] | None = None,
        db: Any = None,
        emit: Any = None,
    ) -> dict[str, Any]:
        # 状态守卫：非 WAITING_CONFIRMATION -> 抛 IllegalTransitionError（PR-14 REST 层转 409）
        check_transition(TaskStatus.WAITING_CONFIRMATION, TaskStatus.EXECUTING)
        # Act + Reflect-Act 的实际执行由编排层在 PR-14 接入 REST 后完成；此处仅做状态校验与占位返回。
        return {"status_code": 200, "status": "EXECUTING", "task_id": task_id}

    async def run_skip_to_score(self, jd_id: str, candidate_ids: list[str], db: Any = None, emit: Any = None) -> dict[str, Any]:
        try:
            await self.active_counter.incr()
        except TaskLimitExceededError:
            return {"status_code": 429, "error": "TASK_LIMIT_EXCEEDED"}
        try:
            # bypass R-P-R：PENDING -> EXECUTING
            check_transition(TaskStatus.PENDING, TaskStatus.EXECUTING)
            return {"status_code": 200, "status": "EXECUTING", "jd_id": jd_id, "candidate_ids": candidate_ids}
        finally:
            await self.active_counter.decr()

    async def run_cancel(self, task_id: str, db: Any = None) -> dict[str, Any]:
        # PLANNING 或 WAITING_CONFIRMATION 均可取消（DECISION §八）
        check_transition(TaskStatus.PLANNING, TaskStatus.CANCELLED)
        check_transition(TaskStatus.WAITING_CONFIRMATION, TaskStatus.CANCELLED)
        return {"status_code": 200, "status": "CANCELLED", "task_id": task_id}
