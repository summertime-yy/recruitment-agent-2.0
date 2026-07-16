"""S4-03 Schema 层测试（TEST-PLAN §2）。"""
import pytest
from pydantic import ValidationError

from app.schemas.match import (
    BatchMatchRequest,
    MatchRankingItem,
    MatchRankingResponse,
    MatchScoreRequest,
    MatchScoreResponse,
)

_DIM = {
    "skill_match": {"score": 80, "rationale": "ok", "matched": ["Python"], "missing": []},
    "experience_match": {"score": 70, "rationale": "ok", "years_required": "3", "years_actual": "4"},
    "education_match": {"score": 90, "rationale": "ok", "required": "本科", "actual": "硕士"},
    "overall_reasoning": "综合良好",
}


def test_match_score_response_serializes_dimension() -> None:
    resp = MatchScoreResponse.model_validate(
        {
            "score_id": "ms_abc",
            "jd_id": "j1",
            "resume_id": "r1",
            "overall_score": 79.0,
            "dimension_scores": _DIM,
            "matching_skill_id": "jd-candidate-matching",
            "matching_skill_version": "1.0.0",
            "skill_execution_id": 1,
            "resume_updated_at_snapshot": None,
            "jd_updated_at_snapshot": None,
            "status": "COMPLETED",
            "error_message": None,
            "created_at": "2026-07-16T00:00:00",
            "updated_at": "2026-07-16T00:00:00",
        }
    )
    assert resp.dimension_scores.skill_match.score == 80
    assert resp.dimension_scores.overall_reasoning == "综合良好"
    assert resp.is_stale is False


def test_match_score_request_validates_ids_length() -> None:
    with pytest.raises(ValidationError):
        MatchScoreRequest(jd_id="x" * 60, resume_id="r1")


def test_match_score_request_ok() -> None:
    req = MatchScoreRequest(jd_id="j1", resume_id="r1")
    assert req.force is False


def test_batch_match_request_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        BatchMatchRequest(jd_id="j1", limit=0)
    with pytest.raises(ValidationError):
        BatchMatchRequest(jd_id="j1", limit=999)


def test_ranking_response_holds_items() -> None:
    item = MatchRankingItem(
        score_id="ms_1",
        resume_id="r1",
        candidate_name="张三",
        overall_score=88.0,
        dimension_scores=_DIM,
        is_stale=False,
        created_at="2026-07-16T00:00:00",
    )
    resp = MatchRankingResponse(jd_id="j1", total=1, items=[item])
    assert resp.items[0].overall_score == 88.0
