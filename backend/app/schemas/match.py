from datetime import datetime

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    score: float = Field(..., ge=0, le=100)
    rationale: str
    matched: list[str] | None = None
    missing: list[str] | None = None
    required: str | None = None
    actual: str | None = None
    years_required: str | None = None
    years_actual: str | None = None


class DimensionScoresPayload(BaseModel):
    skill_match: DimensionScore
    experience_match: DimensionScore
    education_match: DimensionScore
    overall_reasoning: str


class MatchScoreRequest(BaseModel):
    jd_id: str = Field(..., max_length=50)
    resume_id: str = Field(..., max_length=50)
    force: bool = False


class BatchMatchRequest(BaseModel):
    jd_id: str = Field(..., max_length=50)
    resume_ids: list[str] | None = None
    limit: int | None = Field(None, ge=1, le=200)
    force: bool = False


class MatchScoreResponse(BaseModel):
    score_id: str
    jd_id: str
    resume_id: str
    overall_score: float
    dimension_scores: DimensionScoresPayload
    matching_skill_id: str | None = None
    matching_skill_version: str | None = None
    skill_execution_id: int | None = None
    resume_updated_at_snapshot: datetime | None = None
    jd_updated_at_snapshot: datetime | None = None
    status: str
    error_message: str | None = None
    is_stale: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MatchRankingItem(BaseModel):
    score_id: str
    resume_id: str
    candidate_name: str | None = None
    overall_score: float
    dimension_scores: DimensionScoresPayload
    is_stale: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchRankingResponse(BaseModel):
    jd_id: str
    total: int
    items: list[MatchRankingItem]


class BatchTaskResponse(BaseModel):
    task_id: str
    jd_id: str
    total_submitted: int
    submitted_at: datetime


class BatchTaskStatusResponse(BaseModel):
    task_id: str
    jd_id: str
    total: int
    completed: int
    failed: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
