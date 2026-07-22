import logging
from pathlib import Path
from typing import Any

from app.agent.base_skill import BaseSkill

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent / "skills"


class SkillRegistry:
    def __init__(self, skills_dir: Path | None = None):
        self._skills: dict[str, BaseSkill] = {}
        self._skills_dir = skills_dir or _SKILLS_DIR
        self._task_type_to_tool_name: dict[str, str] = {}
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        if not self._skills_dir.exists():
            logger.warning(f"Skills directory not found: {self._skills_dir}")
            return

        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            self._load_skill(skill_dir)

        # PR-17（追债项 10 Y 方向）：自动派生 task_type → tool_name 映射表。
        # 权威源单一 = skill.yaml 的 task_type 字段；冲突时启动即 fail-fast raise，
        # 避免运行时 silent 冲突（内部 skill 与无 task_type 的 skill 一律跳过）。
        self._task_type_to_tool_name = {}
        for skill in self._skills.values():
            if getattr(skill, "internal", False) or not getattr(skill, "task_type", None):
                continue
            task_type = skill.task_type
            if task_type in self._task_type_to_tool_name:
                existing = self._task_type_to_tool_name[task_type]
                raise ValueError(f"task_type conflict: '{task_type}' claimed by '{existing}' and '{skill.skill_id}'")
            self._task_type_to_tool_name[task_type] = skill.skill_id

    def _load_skill(self, skill_dir: Path) -> None:
        try:
            versions = sorted(
                [d for d in skill_dir.iterdir() if d.is_dir() and d.name.startswith("v")],
                reverse=True,
            )
            if not versions:
                for item in skill_dir.iterdir():
                    if item.is_file() and item.suffix in (".yaml", ".yml") and item.name == "skill.yaml":
                        versions = [skill_dir]
                        break

            if not versions:
                logger.warning(f"No version directories found in {skill_dir}")
                return

            latest_version_dir = versions[0]
            skill = BaseSkill(skill_dir=latest_version_dir)
            self._skills[skill.skill_id] = skill
            logger.info(f"Loaded skill: {skill.skill_id} v{skill.version}")
        except Exception as e:
            logger.error(f"Failed to load skill from {skill_dir}: {e}")

    def get_skill(self, skill_id: str) -> BaseSkill | None:
        return self._skills.get(skill_id)

    def get(self, skill_id: str) -> BaseSkill | None:
        """全量查询（含 internal Skill），供 Orchestrator engine 内部调用。"""
        return self._skills.get(skill_id)

    def list_dispatchable(self, task_type: str | None = None) -> list[BaseSkill]:
        """可分发 Skill 列表（排除 internal=True），供 Tool Router 调用。

        task_type 可选：提供时进一步按任务类型过滤（skill 未声明 task_type 则跳过该维度）。
        """
        result = [s for s in self._skills.values() if not getattr(s, "internal", False)]
        if task_type is not None:
            result = [s for s in result if getattr(s, "task_type", None) == task_type]
        return result

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {
                "skill_id": s.skill_id,
                "skill_name": s.skill_name,
                "version": s.version,
                "description": s.description,
            }
            for s in self._skills.values()
        ]

    def register_skill(self, skill: BaseSkill) -> None:
        self._skills[skill.skill_id] = skill
        logger.info(f"Registered skill: {skill.skill_id} v{skill.version}")

    def get_tool_name_for_task_type(self, task_type: str) -> str | None:
        """PR-17（追债项 10 Y 方向）：task_type → tool_name 查询。

        映射由 ``_load_all_skills`` 自动派生；本 PR 内部未消费（plan 侧走 Markdown
        清单动态注入），仅暴露给后续 PR（如未来 reason 侧改动态注入方案 C）。
        """
        return self._task_type_to_tool_name.get(task_type)


_registry_instance: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = SkillRegistry()
    return _registry_instance
