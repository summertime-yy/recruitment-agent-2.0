"""Hydration middleware · PR-26 / PR-28.

在 ToolRouter.dispatch 之前，为数据型 skill 从 DB 补齐 tool_input 缺失字段。
Skill 保持纯函数 · 单点注入 · 显式静态注册表。

PR-26 S3.3 边界：当 db 为 None 时，hydration **必须**抛
``ToolParamError("hydration for '<tool>' requires a db session")``，
**禁止**继续静默返回 ``{}``（否则下游 skill 拿空 tool_input 报 LLM 'required
property' 错、Task 留下"反解析成功"假阳性）。

PR-28 S3.2：``HYDRATION_HINTS`` 是面向 plan LLM 的中文提示语，**配套**
``engine._format_dispatchable_tools`` 使用——告诉 LLM 哪些字段由系统从
数据库自动补齐、它只需提供哪些最小 key。
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from app.agent.orchestrator.tool_router import ToolParamError
from app.models.resume import Resume

logger = logging.getLogger(__name__)

HydrationFn = Callable[[dict[str, Any], Any], Awaitable[dict[str, Any]]]


async def _hydrate_candidate_profile(tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """从 resumes 表补 parsed_content + existing_tags 到 candidate-profile 的 tool_input。

    - 键：``candidate_id`` / ``resume_id``（单数字符串，来自 plan LLM 的 tool_input）
    - PR-28 Q3-A：兼容 ``candidate_ids`` / ``resume_ids`` 单元素数组（LLM 非确定性防御层）；
      多元素直接抛 ToolParamError 并指向 candidate-merge（**不静默取首个**）
    - 未提供任何候选人 ID → ToolParamError
    - resume 不存在 → ToolParamError
    - parsed_content 为 None（parse_status != PARSED）→ ToolParamError
    """
    cid = tool_input.get("candidate_id") or tool_input.get("resume_id")
    if not cid:
        # PR-28 Q3-A：LLM 常输出复数键 + 数组（MVP-VERIFY v2 §4.1 实测）
        for plural_key in ("candidate_ids", "resume_ids"):
            vals = tool_input.get(plural_key)
            if not vals:
                continue
            if len(vals) > 1:
                raise ToolParamError(
                    f"candidate-profile handles exactly one candidate; got {len(vals)} "
                    f"in '{plural_key}' — use candidate-merge for multiple resumes"
                )
            cid = vals[0]
            logger.warning(
                "candidate-profile tool_input used plural key '%s'; "
                "expected singular 'candidate_id' (PR-28 compat path)",
                plural_key,
            )
            break
    if not cid:
        raise ToolParamError("candidate-profile requires 'candidate_id' in tool_input")
    r = await db.execute(select(Resume).where(Resume.resume_id == cid))
    row = r.scalars().first()
    if row is None:
        raise ToolParamError(f"candidate resume not found: {cid}")
    if row.parsed_content is None:
        raise ToolParamError(f"candidate resume not parsed: {cid}")
    return {
        **tool_input,
        "parsed_content": row.parsed_content,
        "existing_tags": list(row.tags or []),
    }


async def _hydrate_candidate_merge(tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """为 candidate-merge 的 resumes 列表每个 item 从 resumes 表补齐字段。

    - 只补 item 上没有的字段（不覆盖 LLM 显式给出的）
    - 每个 item 必须有 resume_id；任一 resume 不存在 → ToolParamError
    - parsed_content 为 None 允许（candidate-merge 对空 parsed_content 有兜底）
    """
    items = tool_input.get("resumes") or []
    if not items:
        raise ToolParamError("candidate-merge requires non-empty 'resumes' in tool_input")
    hydrated: list[dict[str, Any]] = []
    for item in items:
        rid = item.get("resume_id")
        if not rid:
            raise ToolParamError("candidate-merge resume item missing 'resume_id'")
        r = await db.execute(select(Resume).where(Resume.resume_id == rid))
        row = r.scalars().first()
        if row is None:
            raise ToolParamError(f"candidate resume not found: {rid}")
        hydrated.append({
            "resume_id": rid,
            "candidate_name": item.get("candidate_name") or row.candidate_name,
            "parsed_content": item.get("parsed_content") or row.parsed_content or {},
            "tags": item.get("tags") or list(row.tags or []),
            "duplicate_of_resume_id": item.get("duplicate_of_resume_id") or row.duplicate_of_resume_id,
        })
    return {**tool_input, "resumes": hydrated}


HYDRATION_RULES: dict[str, HydrationFn] = {
    "candidate-profile": _hydrate_candidate_profile,
    "candidate-merge": _hydrate_candidate_merge,
}


# PR-28 Q2-A (commit 3): HYDRATION_HINTS is the Chinese hint rendered next
# to a hydration-backed skill in the plan prompt.  It tells the plan LLM
# which fields are filled in by the system from the database (so it
# should not output them) and which minimum keys it must provide.
# key MUST match HYDRATION_RULES exactly (TC-PR28-3 asserts the keys
# align and candidate-profile's hint contains '由系统从数据库自动补齐').
HYDRATION_HINTS: dict[str, str] = {
    "candidate-profile": (
        "注意：`parsed_content` / `existing_tags` 由系统从数据库自动补齐，**你不要填写**。"
        "你只需提供 `candidate_id`（字符串，单个候选人的 resume_id，如 `res_xxxx`）。"
    ),
    "candidate-merge": (
        "注意：每个 resume item 的 `candidate_name` / `parsed_content` / `tags` / "
        "`duplicate_of_resume_id` 由系统从数据库自动补齐，**你不要填写**。"
        "你只需提供 `resumes: [{resume_id: \"res_xxx\"}, {resume_id: \"res_yyy\"}]`"
        "（**至少 2 个**，用于判定是否为同一候选人的重复简历）。"
    ),
}


async def hydrate_tool_input(tool_name: str, tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """按 HYDRATION_RULES 查找 hydrate fn 并调用；未登记的 tool_name 原样返回。"""
    fn = HYDRATION_RULES.get(tool_name)
    if fn is None:
        return tool_input
    if db is None:
        raise ToolParamError(f"hydration for '{tool_name}' requires a db session")
    return await fn(tool_input, db)
