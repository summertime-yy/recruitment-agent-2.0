from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JDGenerateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=100, description="职位名称")
    department: str | None = Field(None, max_length=50, description="所属部门")
    level: str | None = Field(None, max_length=20, description="职级，如P6-P8")
    location: str | None = Field(None, max_length=100, description="工作地点")
    job_type: str | None = Field(None, max_length=30, description="工作类型：全职/兼职/实习")
    recruit_type: str | None = Field(None, max_length=30, description="招聘类型：社招/校招/内推")
    headcount: int | None = Field(1, ge=1, le=100, description="招聘人数")
    experience_years: str | None = Field(None, max_length=30, description="经验年限，如3-5年")
    education_requirement: str | None = Field(None, max_length=30, description="学历要求，如本科及以上")
    salary_range: str | None = Field(None, max_length=50, description="薪资范围")
    description: str = Field(..., min_length=10, description="职位需求描述")
    requirements: list[str] | None = Field(None, description="硬性要求列表")
    required_skills: list[str] | None = Field(None, description="必备技能列表")
    preferred_skills: list[str] | None = Field(None, description="加分技能列表")
    created_by: str | None = Field(None, max_length=50, description="创建人ID")


class JDUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=100)
    department: str | None = None
    level: str | None = None
    location: str | None = None
    job_type: str | None = None
    recruit_type: str | None = None
    headcount: int | None = Field(None, ge=1, le=100)
    experience_years: str | None = None
    education_requirement: str | None = None
    salary_range: str | None = None
    summary: str | None = None
    responsibilities: list[str] | None = None
    requirements: list[str] | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    compliance_check: dict[str, Any] | None = None
    status: str | None = Field(None, pattern="^(DRAFT|PUBLISHED|ARCHIVED)$")


class JDResponse(BaseModel):
    jd_id: str
    title: str
    department: str | None = None
    level: str | None = None
    location: str | None = None
    job_type: str | None = None
    recruit_type: str | None = None
    headcount: int | None = None
    experience_years: str | None = None
    education_requirement: str | None = None
    salary_range: str | None = None
    summary: str | None = None
    responsibilities: list[str] | None = None
    requirements: list[str] | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    compliance_check: dict[str, Any] | None = None
    template_id: str | None = None
    created_by: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JDListResponse(BaseModel):
    items: list[JDResponse]
    total: int
    page: int
    page_size: int


class JDGenerateResponse(BaseModel):
    jd: JDResponse
    skill_execution_id: int
    execution_time_ms: int
    validation_score: float
