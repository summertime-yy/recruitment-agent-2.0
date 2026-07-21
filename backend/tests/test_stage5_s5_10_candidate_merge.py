"""S5-10 · candidate-merge Skill（PR-15 交付物，绿态）。

归属 PR：PR-15（TASKS-STAGE5.md S5-10）
覆盖用例（TC-S5-10-1..4）：
- TC-S5-10-1 高置信度合并：mock LLM 返回 MERGE → result.output["action"] == "MERGE"
- TC-S5-10-2 低置信度建议：mock LLM 返回 SUGGEST → action == "SUGGEST"
- TC-S5-10-3 冲突保持分离：mock LLM 返回 KEEP_SEPARATE → action == "KEEP_SEPARATE"
- TC-S5-10-4 schema 校验失败降级：mock LLM 返回非法 enum → result.success is False

约定：本文件不依赖真实 DB / LLM。通过 monkeypatch `app.agent.llm_adapter.call_llm_json`
注入 mock 输出，直接对从 skill 目录加载的 `BaseSkill` 调用 `execute`。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agent.base_skill import BaseSkill

SKILL_DIR = Path(__file__).resolve().parents[1] / "app" / "agent" / "skills" / "candidate_merge" / "v1_0_0"

# 两份高度相似简历（电话一致），用于 1/2/3 的正向场景与 4 的降级场景输入
_TWO_RESUMES: dict[str, Any] = {
    "resumes": [
        {
            "resume_id": "res_a",
            "candidate_name": "张三",
            "parsed_content": {"phone": "13800000000", "skills": ["Python"]},
            "tags": [],
            "duplicate_of_resume_id": None,
        },
        {
            "resume_id": "res_b",
            "candidate_name": "张三",
            "parsed_content": {"phone": "13800000000", "skills": ["Python", "Go"]},
            "tags": [],
            "duplicate_of_resume_id": "res_a",
        },
    ]
}


def _patch_llm(monkeypatch, payload: dict[str, Any]) -> None:
    async def _fake(system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return payload

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)


@pytest.mark.asyncio
async def test_tc_s5_10_1_high_confidence_merge(monkeypatch):
    """高置信度合并：mock 返回 MERGE → action == MERGE 且 master_resume_id 落地。"""
    _patch_llm(
        monkeypatch,
        {
            "action": "MERGE",
            "master_resume_id": "res_a",
            "merged_fields": {"name": "张三", "phone": "13800000000"},
            "confidence": 0.95,
            "conflicts": [],
            "recommendation": "电话一致，判定为同一人",
        },
    )
    skill = BaseSkill(SKILL_DIR)
    result = await skill.execute(_TWO_RESUMES)

    assert result.success is True
    assert result.output["action"] == "MERGE"
    assert result.output["master_resume_id"] == "res_a"
    assert result.output["confidence"] == 0.95


@pytest.mark.asyncio
async def test_tc_s5_10_2_low_confidence_suggest(monkeypatch):
    """低置信度建议：mock 返回 SUGGEST → action == SUGGEST。"""
    _patch_llm(
        monkeypatch,
        {
            "action": "SUGGEST",
            "master_resume_id": None,
            "merged_fields": {},
            "confidence": 0.4,
            "conflicts": [],
            "recommendation": "联系方式不同，建议人工复核",
        },
    )
    skill = BaseSkill(SKILL_DIR)
    result = await skill.execute(_TWO_RESUMES)

    assert result.success is True
    assert result.output["action"] == "SUGGEST"
    assert result.output["master_resume_id"] is None


@pytest.mark.asyncio
async def test_tc_s5_10_3_conflict_keep_separate(monkeypatch):
    """冲突保持分离：mock 返回 KEEP_SEPARATE → action == KEEP_SEPARATE 且带 conflicts。"""
    _patch_llm(
        monkeypatch,
        {
            "action": "KEEP_SEPARATE",
            "master_resume_id": None,
            "merged_fields": {},
            "confidence": 0.1,
            "conflicts": [{"field": "phone", "values": ["13800000000", "13900000000"]}],
            "recommendation": "电话邮箱均不同，判定为不同人",
        },
    )
    skill = BaseSkill(SKILL_DIR)
    result = await skill.execute(_TWO_RESUMES)

    assert result.success is True
    assert result.output["action"] == "KEEP_SEPARATE"
    assert result.output["conflicts"]


@pytest.mark.asyncio
async def test_tc_s5_10_4_schema_invalid_degrade(monkeypatch):
    """schema 校验失败降级：mock 返回非法 action 枚举 → result.success is False。"""
    _patch_llm(
        monkeypatch,
        {
            "action": "INVALID_ENUM",
            "confidence": 0.5,
            "recommendation": "坏枚举",
        },
    )
    skill = BaseSkill(SKILL_DIR)
    result = await skill.execute(_TWO_RESUMES)

    assert result.success is False
    assert result.error_message
