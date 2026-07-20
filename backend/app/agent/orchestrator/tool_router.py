"""S5-04 · Tool Router（PR-11 交付物，scaffold）。

本文件为 **C3 scaffold**：仅定义模块结构、内置工具常量、错误类与 ``route_task_type``
纯函数。``ToolRouter.dispatch()`` 与内置工具执行逻辑在 **C4** 落地。

设计（最终态，C4 实现）：
- ``dispatch(tool_name, tool_input, db)``：将 ``PlanStep.tool_name`` 路由到
  内置工具（``BUILTIN_TOOLS``）或可分发 Skill（Registry 内、非 internal）。
- ``route_task_type(reason_output)``：从 ReasonOutput 提取 ``task_type``（缺失/未知 → ``"unknown"``）。

错误类：``UnknownToolError`` / ``SkillNotDispatchableError`` / ``ToolParamError``。
"""

from __future__ import annotations

from typing import Any

from app.agent.skill_registry import SkillRegistry, get_skill_registry


class UnknownToolError(Exception):
    """tool_name 既非内置工具也非已注册 Skill。"""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Unknown tool: {tool_name}")


class SkillNotDispatchableError(Exception):
    """tool_name 命中 internal Skill，Tool Router 拒绝直接分发。"""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Skill is not dispatchable (internal): {tool_name}")


class ToolParamError(Exception):
    """工具入参缺失或非法（jsonschema 校验失败 / 业务必填缺失）。"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# 内置工具定义（input_schema 用于入参校验；实现见 C4 ToolRouter._execute_builtin）。
BUILTIN_TOOLS: dict[str, dict[str, Any]] = {
    "search_resumes": {
        "description": "从简历库中按关键词/技能/标签/状态检索候选人摘要",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "简历标题/文件名/候选人名的模糊匹配关键词（必填，避免全表扫）",
                },
                "skill": {"type": "string", "description": "技能标签精确匹配（如 'Python'、'React'）"},
                "tag": {"type": "string", "description": "候选人标签"},
                "candidate_status": {
                    "type": "string",
                    "description": "候选状态（NEW/SCREENING_PASSED/SCREENING_REJECTED/INTERVIEWING/OFFERED/ARCHIVED）",
                },
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 10, "maximum": 50},
            },
            "required": ["keyword"],
        },
    },
    "read_jd": {
        "description": "读取单条 JD 完整结构化字段",
        "input_schema": {
            "type": "object",
            "properties": {
                "jd_id": {
                    "type": "string",
                    "pattern": "^jd_[a-zA-Z0-9]+$",
                    "description": "JD 唯一标识（jd_ 前缀）",
                },
            },
            "required": ["jd_id"],
        },
    },
}


class ToolRouter:
    """将 PlanStep.tool_name 路由到内置工具或可分发 Skill（C4 落地核心逻辑）。"""

    def __init__(self, registry: SkillRegistry | None = None):
        self.registry = registry or get_skill_registry()

    def list_builtin_tools(self) -> list[str]:
        return list(BUILTIN_TOOLS.keys())


def route_task_type(reason_output: dict[str, Any]) -> str:
    """从 ReasonOutput 提取 task_type；缺失或未知返回 'unknown'（与 skill.yaml task_type 1:1 对齐）。"""
    return reason_output.get("task_type") or "unknown"
