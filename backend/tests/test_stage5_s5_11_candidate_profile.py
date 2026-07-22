"""S5-11 · candidate-profile Skill（PR-16 交付物，red→green）。

归属 PR：PR-16（TASKS-STAGE5.md S5-11）
覆盖用例（TC-S5-11-1..4）：
- TC-S5-11-1 正常生成：mock LLM 返回合法四字段 → profile_tags 非空且 success
- TC-S5-11-2 与手工标签合并去重：mock LLM 返已归一 payload → profile_tags 无重复、长度符合
- TC-S5-11-3 schema 校验失败降级：mock LLM 缺必填字段 → success is False（不写库）
- TC-S5-11-4 空 parsed_content 边界：mock LLM 返空结果 → success=True 且 profile_tags 为空

约定：本文件不依赖真实 DB / LLM。通过 monkeypatch `app.agent.llm_adapter.call_llm_json`
注入 mock 输出，直接对从 skill 目录加载的 `BaseSkill` 调用 `execute`。

注意：阶段 1 为 red-test 骨架，`candidate_profile/v1_0_0/skill.yaml` 尚未落地，
首行 `assert skill.skill_id == "candidate-profile"` 守卫断言会失败（红）；
阶段 2 三件套落地后该断言通过，四用例转绿。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agent.base_skill import BaseSkill

SKILL_DIR = Path(__file__).resolve().parents[1] / "app" / "agent" / "skills" / "candidate_profile" / "v1_0_0"

# 一份正常简历解析内容，供 1/2/3 的正向场景入参
_NORMAL_PARSED: dict[str, Any] = {
    "name": "张三",
    "skills": ["Python", "SQL"],
    "experience_years": 5,
    "highlights": ["主导过千万级用户系统"],
}

# 四字段齐备的合法 mock 输出
_LEGAL_OUTPUT: dict[str, Any] = {
    "profile_tags": ["Python", "SQL", "Backend"],
    "summary": "5 年经验后端工程师，主导过千万级用户系统",
    "strengths": ["扎实的分布式经验", "主动 owner 意识"],
    "risks": ["近期存在空窗期"],
}


def _patch_llm(monkeypatch, payload: dict[str, Any]) -> None:
    async def _fake(system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return payload

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)


@pytest.mark.asyncio
async def test_tc_s5_11_1_profile_tags_non_empty(monkeypatch):
    """正常生成：mock 返回合法四字段 → profile_tags 非空且 success。"""
    _patch_llm(monkeypatch, _LEGAL_OUTPUT)
    skill = BaseSkill(SKILL_DIR)
    assert skill.skill_id == "candidate-profile"  # 守卫：三件套落地前为红
    result = await skill.execute({"parsed_content": _NORMAL_PARSED, "existing_tags": []})

    assert result.success is True
    assert result.output["profile_tags"]
    assert len(result.output["profile_tags"]) >= 1


@pytest.mark.asyncio
async def test_tc_s5_11_2_merge_existing_tags_dedup(monkeypatch):
    """与手工标签合并去重：mock 返已归一 payload → profile_tags 无重复、长度符合。"""
    # 测的是 Skill 契约（output schema 通过、返值可读），不测 LLM 归一能力
    _patch_llm(
        monkeypatch,
        {
            "profile_tags": ["Python", "SQL"],
            "summary": "合并已有手工标签后的画像",
            "strengths": ["熟练 Python 后端开发"],
            "risks": [],
        },
    )
    skill = BaseSkill(SKILL_DIR)
    assert skill.skill_id == "candidate-profile"
    result = await skill.execute({"parsed_content": _NORMAL_PARSED, "existing_tags": ["Python"]})

    assert result.success is True
    tags = result.output["profile_tags"]
    assert set(tags) == {"Python", "SQL"}
    assert len(tags) == 2


@pytest.mark.asyncio
async def test_tc_s5_11_3_schema_invalid_degrade(monkeypatch):
    """schema 校验失败降级：mock 缺必填字段 → success is False。"""
    _patch_llm(
        monkeypatch,
        {
            # 缺失 profile_tags / strengths / risks 三个必填数组字段
            "summary": "只给 summary，缺其余字段",
        },
    )
    skill = BaseSkill(SKILL_DIR)
    assert skill.skill_id == "candidate-profile"
    result = await skill.execute({"parsed_content": _NORMAL_PARSED, "existing_tags": []})

    assert result.success is False
    assert result.error_message


@pytest.mark.asyncio
async def test_tc_s5_11_4_empty_parsed_content(monkeypatch):
    """空 parsed_content 边界：mock 返空结果 → success=True 且 profile_tags 为空。"""
    _patch_llm(
        monkeypatch,
        {
            "profile_tags": [],
            "summary": "简历内容为空",
            "strengths": [],
            "risks": [],
        },
    )
    skill = BaseSkill(SKILL_DIR)
    assert skill.skill_id == "candidate-profile"
    result = await skill.execute({"parsed_content": {}, "existing_tags": []})

    assert result.success is True
    assert result.output["profile_tags"] == []
