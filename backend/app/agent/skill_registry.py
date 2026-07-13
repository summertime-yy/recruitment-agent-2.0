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
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        if not self._skills_dir.exists():
            logger.warning(f"Skills directory not found: {self._skills_dir}")
            return

        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            self._load_skill(skill_dir)

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


_registry_instance: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = SkillRegistry()
    return _registry_instance
