"""测试工厂函数：构造最小可用的模型实例（不自动插入，由测试负责 add/flush）。

PR-28 commit 1 隔离修复：
- `build_skill` / `build_skill_execution_log` 的默认 `skill_id` 加 uuid 后缀，
  避免 dev DB 中已存在同名 Skill 行（基线 1 failed：单跑即撞 skills_pkey）。
- 仍可显式传 `skill_id="..."` 覆盖。
"""

from uuid import uuid4

from app.core.time import utcnow_aware
from app.models import JD, Resume, Skill, SkillExecutionLog
from app.models.task import Task


def build_skill(**kwargs) -> Skill:
    data: dict = {
        "skill_id": f"jd-candidate-matching-{uuid4().hex[:6]}",
        "skill_name": "JD 候选人匹配",
        "current_version": "1.0.0",
        "status": "ACTIVE",
    }
    data.update(kwargs)
    return Skill(**data)


def build_jd(**kwargs) -> JD:
    data: dict = {"title": "测试后端工程师", "status": "DRAFT"}
    data.update(kwargs)
    return JD(**data)


def build_resume(**kwargs) -> Resume:
    data: dict = {
        "candidate_name": "张三",
        "file_name": "zhangsan.pdf",
        "file_path": "resumes/zhangsan.pdf",
        "file_type": "pdf",
        "parse_status": "PARSED",
        "parsed_content": {"skills": ["Python", "FastAPI"], "summary": "3年后端经验"},
    }
    data.update(kwargs)
    return Resume(**data)


def build_skill_execution_log(**kwargs) -> SkillExecutionLog:
    data: dict = {
        "skill_id": f"jd-candidate-matching-{uuid4().hex[:6]}",
        "version": "1.0.0",
        "execution_status": "SUCCESS",
        "executed_at": utcnow_aware(),
        "validation_score": 0.9,
    }
    data.update(kwargs)
    return SkillExecutionLog(**data)


def build_task(**kwargs) -> Task:
    """PR-28 commit 5: minimum-viable Task row for writer / engine tests.

    `user_message` is NOT NULL on the model; default to a short fixture
    string so callers can build a Task with only `task_id` /
    `status` overridden.
    """
    data: dict = {
        "user_message": "fixture task for pr-28",
        "status": "PENDING",
    }
    data.update(kwargs)
    return Task(**data)
