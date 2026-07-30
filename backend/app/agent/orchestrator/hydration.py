"""Hydration middleware · PR-26.

在 ToolRouter.dispatch 之前，为数据型 skill 从 DB 补齐 tool_input 缺失字段。
Skill 保持纯函数 · 单点注入 · 显式静态注册表。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from app.agent.orchestrator.tool_router import ToolParamError
from app.models.resume import Resume

HydrationFn = Callable[[dict[str, Any], Any], Awaitable[dict[str, Any]]]


async def _hydrate_candidate_profile(tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """从 resumes 表补 parsed_content + existing_tags 到 candidate-profile 的 tool_input。

    - 键：``candidate_id``（来自 plan LLM 的 tool_input）
    - 未提供 candidate_id → ToolParamError
    - resume 不存在 → ToolParamError
    - parsed_content 为 None（parse_status != PARSED）→ ToolParamError
    """
    cid = tool_input.get("candidate_id") or tool_input.get("resume_id")
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


async def hydrate_tool_input(tool_name: str, tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """按 HYDRATION_RULES 查找 hydrate fn 并调用；未登记的 tool_name 原样返回。"""
    fn = HYDRATION_RULES.get(tool_name)
    if fn is None:
        return tool_input
    if db is None:
        raise ToolParamError(f"hydration for '{tool_name}' requires a db session")
    return await fn(tool_input, db)
