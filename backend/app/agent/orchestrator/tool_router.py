"""S5-04 · Tool Router（PR-11 交付物）。

职责：
- ``dispatch(tool_name, tool_input, db)``：统一入口，将 ``PlanStep.tool_name`` 路由到
  - 内置工具（``BUILTIN_TOOLS``：``search_resumes`` / ``read_jd``），或
  - 可分发 Skill（``SkillRegistry`` 内、非 internal 的 skill）
- ``route_task_type(reason_output)``：从 ReasonOutput 提取 ``task_type``
  （缺失或未知值 → ``"unknown"``），与 skill.yaml 内 ``task_type`` 字段 1:1 对齐。

错误类：
- ``UnknownToolError``：``tool_name`` 既非内置工具也非已注册 Skill。
- ``SkillNotDispatchableError``：``tool_name`` 命中 internal Skill，Tool Router 拒绝直接分发。
- ``ToolParamError``：工具入参缺失/非法（jsonschema 校验失败或业务必填缺失）。
"""

from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate

from app.agent.base_skill import SkillResult
from app.agent.skill_registry import SkillRegistry, get_skill_registry
from app.services.jd import JDService
from app.services.resume import ResumeService


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


# 内置工具定义：input_schema 用于入参校验；实现见 ToolRouter._execute_builtin。
# 注意：ResumeSummary 不新建 pydantic 模型，直接返回字典（PR-14 REST 层再规范化）。
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


def _validate_tool_input(tool_name: str, tool_input: dict[str, Any]) -> None:
    """按 BUILTIN_TOOLS 的 input_schema 校验；失败抛 ToolParamError。"""
    schema = BUILTIN_TOOLS[tool_name]["input_schema"]
    try:
        validate(instance=tool_input or {}, schema=schema)
    except ValidationError as e:
        raise ToolParamError(f"Invalid input for {tool_name}: {e.message}")


def _build_resume_summary(resume: Any) -> dict[str, Any]:
    """从 Resume ORM 对象提取轻量摘要（不含 raw_text，避免 payload 膨胀）。"""
    skills: list[str] = []
    if getattr(resume, "parsed_content", None):
        skills = resume.parsed_content.get("skills", []) or []
    created_at = getattr(resume, "created_at", None)
    return {
        "resume_id": resume.resume_id,
        "candidate_name": getattr(resume, "candidate_name", None),
        "skills": skills,
        "candidate_status": getattr(resume, "candidate_status", None),
        "created_at": created_at.isoformat() if created_at is not None else None,
    }


def _build_jd_output(jd: Any) -> dict[str, Any]:
    """将 JD ORM 对象转为纯 dict（剔除 SQLAlchemy 内部状态）。"""
    return {k: v for k, v in jd.__dict__.items() if not k.startswith("_")}


class ToolRouter:
    """将 PlanStep.tool_name 路由到内置工具或可分发 Skill。"""

    def __init__(self, registry: SkillRegistry | None = None):
        self.registry = registry or get_skill_registry()

    def list_builtin_tools(self) -> list[str]:
        return list(BUILTIN_TOOLS.keys())

    async def dispatch(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | None = None,
        db: Any = None,
    ) -> SkillResult:
        tool_input = tool_input or {}

        # 1. 内置工具
        if tool_name in BUILTIN_TOOLS:
            return await self._execute_builtin(tool_name, tool_input, db)

        # 2. 分发 Skill
        skill = self.registry.get_skill(tool_name)
        if skill is None:
            raise UnknownToolError(tool_name)
        if getattr(skill, "internal", False):
            raise SkillNotDispatchableError(tool_name)

        return await skill.execute(tool_input)

    async def _execute_builtin(self, tool_name: str, tool_input: dict[str, Any], db: Any) -> SkillResult:
        _validate_tool_input(tool_name, tool_input)

        if db is None:
            raise ToolParamError(f"Builtin tool '{tool_name}' requires a db session")

        if tool_name == "search_resumes":
            service = ResumeService(db)
            items, total = await service.list_resumes(
                keyword=tool_input.get("keyword"),
                skill=tool_input.get("skill"),
                tag=tool_input.get("tag"),
                candidate_status=tool_input.get("candidate_status"),
                page=tool_input.get("page", 1),
                page_size=tool_input.get("page_size", 10),
            )
            summaries = [_build_resume_summary(r) for r in items]
            return SkillResult(
                success=True,
                output={
                    "items": summaries,
                    "total": total,
                    "page": tool_input.get("page", 1),
                    "page_size": tool_input.get("page_size", 10),
                },
            )

        if tool_name == "read_jd":
            service = JDService(db)
            jd = await service.get_jd(tool_input["jd_id"])
            if jd is None:
                raise ToolParamError(f"jd not found: {tool_input['jd_id']}")
            return SkillResult(success=True, output=_build_jd_output(jd))

        raise UnknownToolError(tool_name)


def route_task_type(reason_output: dict[str, Any]) -> str:
    """从 ReasonOutput 提取 task_type；缺失或未知返回 'unknown'。

    与 skill.yaml 内 ``task_type`` 字段 1:1 对齐（如 ``match`` → jd-candidate-matching）。
    """
    return reason_output.get("task_type") or "unknown"
