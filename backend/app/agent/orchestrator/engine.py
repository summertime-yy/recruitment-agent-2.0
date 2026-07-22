"""S5-08 · OrchestratorEngine：R-P-R-A-R 主循环编排（PR-12 + PR-13 + PR-14）。

方法分层（裁定 DECISION §四 Q3 / §二 Q5 / §八 Q7）：
- start_chat          : R -> P -> R 异步化，立即返 {task_id, PLANNING}，后台跑 _background_reason_plan
- _background_reason_plan: R -> P -> Reflect-Plan -> WAITING_CONFIRMATION（PR-14 Q5 异步化）
- run_execute         : A -> R (Act -> Reflect-Act) -> COMPLETED / FAILED（PR-13 后台任务真跑）
- run_skip_to_score   : bypass R-P-R，直接 Act -> COMPLETED / FAILED（PR-13 后台任务真跑，PR-14 真 task_id）
- run_cancel          : PLANNING / WAITING_CONFIRMATION -> CANCELLED

构造依赖注入（DECISION §六 Q6 / §七 / §四 Q1）：
- registry、tool_router 必需可注入
- active_counter、event_buffer、settings、超时以合理默认值提供
- event_buffer 提供时，active_counter 自动选用 RedisActiveCounter（共用同一个 Redis）
- db_updater 可选：Engine 在头尾/终止态回调写 tasks 表（PR-14 Q1 方案 B；INSERT 由 REST 端点侧做）
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.orchestrator import errors as _errors
from app.agent.orchestrator import state_machine
from app.agent.orchestrator.active_counter import (
    ActiveCounter,
    InMemoryActiveCounter,
    RedisActiveCounter,
)
from app.agent.orchestrator.event_buffer import EventBuffer
from app.agent.orchestrator.state_machine import TaskStatus, check_transition
from app.agent.orchestrator.tool_router import BUILTIN_TOOLS, ToolRouter
from app.agent.skill_registry import SkillRegistry, get_skill_registry
from app.core.config import get_settings
from app.core.time import utcnow_naive
from app.schemas.agent import SSEEvent, SSEEventType

logger = logging.getLogger(__name__)

# 供测试从本模块导入（以赋值方式再导出，避免 F401）
TransitionGuard = state_machine.TransitionGuard
IllegalTransitionError = _errors.IllegalTransitionError
TaskLimitExceededError = _errors.TaskLimitExceededError

# db_updater 回调：把 task_id + 字段补丁写进 tasks 表。默认 None（旧测试/纯内存引擎不写库）。
DbUpdater = Callable[[str, dict[str, Any]], Awaitable[None]]

# tool_name -> 任务级 result artifact.type 映射（PR-13 Q6）
_ARTIFACT_TYPE_MAP: dict[str, str] = {
    "create_match_score": "match_score",
    "read_jd": "jd",
    "read_resume": "resume",
    "candidate-merge": "candidate_merge",
    "candidate-profile": "candidate_profile",
}


def _build_artifacts(results: list[Any]) -> list[dict[str, Any]]:
    """把 Act 各步 StepResult 映射为 ResultArtifact 列表（PR-13 Q6）。"""
    out: list[dict[str, Any]] = []
    for r in results:
        if not getattr(r, "success", False) or not getattr(r, "output", None):
            continue
        tool_name = getattr(r, "tool_name", "")
        artifact_type = _ARTIFACT_TYPE_MAP.get(tool_name, "generic")
        output = r.output
        ref_id = None
        if artifact_type == "match_score":
            ref_id = output.get("match_score_id") or output.get("id")
        elif artifact_type == "resume":
            ref_id = output.get("resume_id") or output.get("id")
        elif artifact_type == "jd":
            ref_id = output.get("jd_id") or output.get("id")
        item: dict[str, Any] = {
            "step_id": getattr(r, "step_id", ""),
            "tool_name": tool_name,
            "type": artifact_type,
        }
        if artifact_type == "generic":
            item["data"] = output
        elif ref_id is not None:
            item["ref_id"] = str(ref_id)
        else:
            # 引用型但未提取到 ref_id → 降级为 generic
            item["type"] = "generic"
            item["data"] = output
        out.append(item)
    return out


class OrchestratorEngine:
    def __init__(
        self,
        registry: SkillRegistry | None = None,
        tool_router: ToolRouter | None = None,
        active_counter: ActiveCounter | None = None,
        event_buffer: EventBuffer | None = None,
        settings: Any | None = None,
        skill_timeout_sec: float | None = None,
        phase_timeout_sec: float | None = None,
        task_timeout_sec: float | None = None,
        db_updater: DbUpdater | None = None,
    ):
        self.settings = settings or get_settings()
        self.registry = registry or get_skill_registry()
        self.tool_router = tool_router or ToolRouter(self.registry)
        self.event_buffer = event_buffer
        self.db_updater = db_updater
        self.skill_timeout_sec = skill_timeout_sec if skill_timeout_sec is not None else self.settings.skill_timeout_sec
        self.phase_timeout_sec = phase_timeout_sec if phase_timeout_sec is not None else self.settings.phase_timeout_sec
        self.task_timeout_sec = task_timeout_sec if task_timeout_sec is not None else self.settings.task_timeout_sec
        if active_counter is None:
            if event_buffer is not None:
                active_counter = RedisActiveCounter(event_buffer.redis, limit=self.settings.task_active_limit)
            else:
                active_counter = InMemoryActiveCounter(limit=self.settings.task_active_limit)
        self.active_counter = active_counter

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
    async def run_step_with_timeout(
        self, step: dict[str, Any], tool_router: ToolRouter | None = None
    ) -> dict[str, Any]:
        router = tool_router or self.tool_router
        try:
            sr = await asyncio.wait_for(
                router.dispatch(step.get("tool_name"), step.get("args") or step.get("tool_input") or {}),
                timeout=self.skill_timeout_sec,
            )
            return {"status": "SUCCESS" if sr.success else "FAILED", "events": [], "output": sr.output}
        except TimeoutError:
            return {"status": "FAILED", "events": [{"type": "error", "message": "skill timeout"}], "output": None}

    async def run_task_with_overall_timeout(
        self, task_input: dict[str, Any], tool_router: ToolRouter | None = None
    ) -> dict[str, Any]:
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

    # ---- 端点层：异步 chat（Q5 (b1)）----
    async def start_chat(
        self,
        task_id: str,
        user_message: str,
        context: dict[str, Any] | None = None,
        db_updater: DbUpdater | None = None,
    ) -> dict[str, Any]:
        """发起 R-P-R，立即返 {task_id, PLANNING}（DECISSION §二 (b1)）。

        ``task_id`` 由 REST 端点侧生成并完成 tasks 行 INSERT（Engine 不碰 ORM）；
        本方法仅做活跃计数 + fire-and-forget 后台跑 ``_background_reason_plan``。
        """
        try:
            await self.active_counter.incr()
        except TaskLimitExceededError:
            return {"status_code": 429, "error": "TASK_LIMIT_EXCEEDED"}
        updater = db_updater or self.db_updater
        if updater is not None:
            await updater(
                task_id,
                {"status": "PLANNING", "user_message": user_message, "context": context or {}},
            )
        asyncio.create_task(
            self._background_reason_plan(task_id, user_message, context or {}, updater),
            name=f"orch-reason-plan-{task_id}",
        )
        return {"status_code": 200, "task_id": task_id, "status": "PLANNING"}

    async def _background_reason_plan(
        self,
        task_id: str,
        user_message: str,
        context: dict[str, Any],
        db_updater: DbUpdater | None = None,
    ) -> None:
        """后台 R-P-R：THINKING（一次性）+ PLAN（实时）+ 终态写 tasks（PR-14 Q5）。"""
        emit = self._make_emit(task_id)
        try:
            reason_out = await self.run_reason({"user_input": user_message, "context": context})
            await emit(
                SSEEvent(
                    type=SSEEventType.THINKING,
                    id="0",
                    task_id=task_id,
                    timestamp="",
                    data={"content": reason_out.get("reasoning") or "reasoning completed"},
                )
            )
            reflect_out = await self.run_reflect(reason_out)
            if not reflect_out.get("is_feasible", True):
                await self._write_task(
                    db_updater,
                    task_id,
                    {
                        "status": "WAITING_CONFIRMATION",
                        "error": {"blocking_reason": reflect_out.get("blocking_reason", "")},
                    },
                )
                return
            plan_out = await self.run_plan({"reason_output": reason_out})
            await emit(SSEEvent(type=SSEEventType.PLAN, id="0", task_id=task_id, timestamp="", data=plan_out))
            reflect_plan_out = await self.run_reflect_plan({"plan": plan_out})
            final_steps = reflect_plan_out.get("steps", plan_out.get("steps", []))
            if final_steps != plan_out.get("steps"):
                await emit(
                    SSEEvent(
                        type=SSEEventType.PLAN,
                        id="0",
                        task_id=task_id,
                        timestamp="",
                        data={"steps": final_steps, "reasoning": plan_out.get("reasoning")},
                    )
                )
            final_plan = {"steps": final_steps, "reasoning": plan_out.get("reasoning")}
            await self._write_task(
                db_updater,
                task_id,
                {"status": "WAITING_CONFIRMATION", "plan": final_plan},
            )
        except Exception as e:  # noqa: BLE001 - 后台任务禁止抛异常
            logger.exception("background reason_plan failed for task=%s", task_id)
            await self._write_task(
                db_updater,
                task_id,
                {
                    "status": "FAILED",
                    "error": {"code": "REASON_PLAN_FAILED", "message": str(e)},
                    "finished_at": utcnow_naive(),
                },
            )
            try:
                await emit(
                    SSEEvent(
                        type=SSEEventType.ERROR,
                        id="0",
                        task_id=task_id,
                        timestamp="",
                        data={"code": "REASON_PLAN_FAILED", "message": str(e)},
                    )
                )
                if self.event_buffer is not None:
                    await self.event_buffer.set_terminal_ttl(task_id)
            except Exception:  # noqa: BLE001, S110
                pass
        finally:
            try:
                await self.active_counter.decr()
            except Exception:  # noqa: BLE001, S110
                pass

    @staticmethod
    async def _write_task(db_updater: DbUpdater | None, task_id: str, patch: dict[str, Any]) -> None:
        if db_updater is not None:
            await db_updater(task_id, patch)

    # ---- emit 适配器（PR-13 Q3）----
    def _make_emit(self, task_id: str) -> Any:
        """构造 emit 回调：把 SSEEvent 桥接到 EventBuffer.append。

        EventBuffer.append 负责分配 seq_id + timestamp，这里只用 ev 的
        type / data / step_id（id/timestamp 被 append 内部覆盖）。
        """
        if self.event_buffer is None:

            async def _noop(ev: SSEEvent) -> None:
                return None

            return _noop
        buffer = self.event_buffer

        async def _emit(ev: SSEEvent) -> None:
            await buffer.append(task_id, ev.type, ev.data, ev.step_id)

        return _emit

    # ---- A: Act + Reflect-Act（PR-13 后台真跑）----
    async def run_execute(
        self,
        task_id: str,
        plan: dict[str, Any] | None = None,
        accepted_steps: list[str] | None = None,
        modifications: list[dict[str, Any]] | None = None,
        db: Any = None,
        event_buffer: EventBuffer | None = None,
        db_updater: DbUpdater | None = None,
    ) -> dict[str, Any]:
        # 状态守卫：非 WAITING_CONFIRMATION -> 抛 IllegalTransitionError（PR-14 REST 层转 409）
        check_transition(TaskStatus.WAITING_CONFIRMATION, TaskStatus.EXECUTING)
        try:
            await self.active_counter.incr()
        except TaskLimitExceededError:
            return {"status_code": 429, "error": "TASK_LIMIT_EXCEEDED"}
        buffer = event_buffer or self.event_buffer
        if plan is None:
            plan = {"steps": []}  # PR-14 会从 tasks 表读入真实 plan
        # 应用 accepted_steps 过滤
        if accepted_steps is not None:
            plan = {**plan, "steps": [s for s in (plan.get("steps") or []) if s.get("step_id") in accepted_steps]}
        # 应用 modifications
        if modifications:
            mod_map = {m["step_id"]: m.get("modified_params") for m in modifications}
            plan = {
                **plan,
                "steps": [
                    (
                        {**s, "tool_input": mod_map.get(s.get("step_id"), s.get("tool_input") or s.get("args") or {})}
                        if s.get("step_id") in mod_map
                        else s
                    )
                    for s in (plan.get("steps") or [])
                ],
            }
        # 后台跑（不阻塞 HTTP 响应）；收尾 decr 由 _background_execute 负责
        asyncio.create_task(
            self._background_execute(task_id, plan, buffer, db_updater or self.db_updater),
            name=f"orch-execute-{task_id}",
        )
        return {"status_code": 200, "status": "EXECUTING", "task_id": task_id}

    async def run_skip_to_score(
        self,
        jd_id: str,
        candidate_ids: list[str],
        task_id: str,
        db: Any = None,
        event_buffer: EventBuffer | None = None,
        db_updater: DbUpdater | None = None,
    ) -> dict[str, Any]:
        try:
            await self.active_counter.incr()
        except TaskLimitExceededError:
            return {"status_code": 429, "error": "TASK_LIMIT_EXCEEDED"}
        # bypass R-P-R：跳过 PENDING/PLANNING 直接 EXECUTING（状态守卫移除，端点侧已 INSERT 为 EXECUTING）
        buffer = event_buffer or self.event_buffer
        plan = {
            "steps": [
                {
                    "step_id": f"step_score_{i}",
                    "tool_name": "create_match_score",
                    "tool_input": {"jd_id": jd_id, "resume_id": cid},
                }
                for i, cid in enumerate(candidate_ids)
            ]
        }
        # 后台跑；收尾 decr 由 _background_execute 负责
        asyncio.create_task(
            self._background_execute(task_id, plan, buffer, db_updater or self.db_updater),
            name=f"orch-skip-{task_id}",
        )
        return {
            "status_code": 200,
            "status": "EXECUTING",
            "task_id": task_id,
            "jd_id": jd_id,
            "candidate_ids": candidate_ids,
        }

    async def _background_execute(
        self,
        task_id: str,
        plan: dict[str, Any],
        buffer: EventBuffer | None,
        db_updater: DbUpdater | None = None,
    ) -> None:
        """后台任务：跑 Act + Reflect-Act，收尾发 result 事件 + 设 TTL + 写 tasks 终态（PR-13 Q4 + PR-14 Q1）。

        try/finally 保证无论成功/失败/超时都 decr 活跃计数（PR-13 Q4）。
        """
        from app.agent.orchestrator.act import run_act

        emit = self._make_emit(task_id) if buffer else None
        try:
            # 起始：写 EXECUTING（Q1 方案 B 第 2 处）
            await self._write_task(
                db_updater,
                task_id,
                {"status": "EXECUTING", "started_at": utcnow_naive()},
            )
            results = await asyncio.wait_for(
                run_act(plan, ctx={"task_id": task_id}, emit=emit, tool_router=self.tool_router),
                timeout=self.task_timeout_sec,
            )
            reflect_act_out = await self.run_reflect_act(
                {
                    "step_results": [
                        {"step_id": r.step_id, "tool_name": r.tool_name, "success": r.success, "output": r.output}
                        for r in results
                    ],
                }
            )
            artifacts = _build_artifacts(results)
            result_payload = {"content": reflect_act_out.get("final_result", ""), "artifacts": artifacts}
            if buffer is not None:
                await buffer.append(task_id, SSEEventType.RESULT, result_payload)
                await buffer.set_terminal_ttl(task_id)
            # 终态：写 COMPLETED（Q1 方案 B 第 3 处 - 成功）
            await self._write_task(
                db_updater,
                task_id,
                {"status": "COMPLETED", "finished_at": utcnow_naive(), "result": result_payload},
            )
        except TimeoutError:
            if buffer is not None:
                await buffer.append(
                    task_id,
                    SSEEventType.ERROR,
                    {
                        "code": "TASK_TIMEOUT",
                        "message": "task overall timeout",
                        "recoverable": False,
                    },
                )
                await buffer.set_terminal_ttl(task_id)
            # 终态：写 FAILED (TASK_TIMEOUT)
            await self._write_task(
                db_updater,
                task_id,
                {
                    "status": "FAILED",
                    "finished_at": utcnow_naive(),
                    "error": {"code": "TASK_TIMEOUT", "message": "task overall timeout", "recoverable": False},
                },
            )
        except Exception as e:  # noqa: BLE001 - 后台任务禁止抛异常
            logger.exception("background execute failed for task=%s", task_id)
            if buffer is not None:
                try:
                    await buffer.append(
                        task_id,
                        SSEEventType.ERROR,
                        {
                            "code": "INTERNAL_ERROR",
                            "message": str(e),
                            "recoverable": False,
                        },
                    )
                    await buffer.set_terminal_ttl(task_id)
                except Exception:  # noqa: BLE001, S110
                    pass
            # 终态：写 FAILED (INTERNAL_ERROR)
            await self._write_task(
                db_updater,
                task_id,
                {
                    "status": "FAILED",
                    "finished_at": utcnow_naive(),
                    "error": {"code": "INTERNAL_ERROR", "message": str(e), "recoverable": False},
                },
            )
        finally:
            try:
                await self.active_counter.decr()
            except Exception:  # noqa: BLE001, S110
                pass

    async def run_reflect_act(self, reflect_act_input: dict[str, Any]) -> dict[str, Any]:
        """调 orchestrator-reflect-act Skill，输出 final_result 供 result 事件用（PR-13 Q4）。"""
        skill = self.registry.get("orchestrator-reflect-act")
        if skill is None:
            return {"final_result": "", "issues": []}
        result = await skill.execute(reflect_act_input)
        if not result.success:
            return {"final_result": "", "issues": [result.error_message or "reflect-act failed"]}
        return result.output or {}

    async def run_cancel(self, task_id: str, db: Any = None) -> dict[str, Any]:
        # PLANNING 或 WAITING_CONFIRMATION 均可取消（DECISION §八）
        check_transition(TaskStatus.PLANNING, TaskStatus.CANCELLED)
        check_transition(TaskStatus.WAITING_CONFIRMATION, TaskStatus.CANCELLED)
        return {"status_code": 200, "status": "CANCELLED", "task_id": task_id}
