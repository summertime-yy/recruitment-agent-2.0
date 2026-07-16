"""测试工厂函数：构造最小可用的模型实例（不自动插入，由测试负责 add/flush）。"""
from datetime import datetime

from app.models import JD, Resume, Skill, SkillExecutionLog


def build_skill(**kwargs) -> Skill:
    data: dict = {
        "skill_id": "jd-candidate-matching",
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
        "skill_id": "jd-candidate-matching",
        "version": "1.0.0",
        "execution_status": "SUCCESS",
        "executed_at": datetime.utcnow(),
        "validation_score": 0.9,
    }
    data.update(kwargs)
    return SkillExecutionLog(**data)
