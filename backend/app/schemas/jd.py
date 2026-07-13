from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class JDGenerateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=100, description="职位名称")
    department: Optional[str] = Field(None, max_length=50, description="所属部门")
    level: Optional[str] = Field(None, max_length=20, description="职级，如P6-P8")
    location: Optional[str] = Field(None, max_length=100, description="工作地点")
    job_type: Optional[str] = Field(None, max_length=30, description="工作类型：全职/兼职/实习")
    recruit_type: Optional[str] = Field(None, max_length=30, description="招聘类型：社招/校招/内推")
    headcount: Optional[int] = Field(1, ge=1, le=100, description="招聘人数")
    experience_years: Optional[str] = Field(None, max_length=30, description="经验年限，如3-5年")
    education_requirement: Optional[str] = Field(None, max_length=30, description="学历要求，如本科及以上")
    salary_range: Optional[str] = Field(None, max_length=50, description="薪资范围")
    description: str = Field(..., min_length=10, description="职位需求描述")
    requirements: Optional[list[str]] = Field(None, description="硬性要求列表")
    required_skills: Optional[list[str]] = Field(None, description="必备技能列表")
    preferred_skills: Optional[list[str]] = Field(None, description="加分技能列表")
    created_by: Optional[str] = Field(None, max_length=50, description="创建人ID")


class JDUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=100)
    department: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    recruit_type: Optional[str] = None
    headcount: Optional[int] = Field(None, ge=1, le=100)
    experience_years: Optional[str] = None
    education_requirement: Optional[str] = None
    salary_range: Optional[str] = None
    summary: Optional[str] = None
    responsibilities: Optional[list[str]] = None
    requirements: Optional[list[str]] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    compliance_check: Optional[dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(DRAFT|PUBLISHED|ARCHIVED)$")


class JDResponse(BaseModel):
    jd_id: str
    title: str
    department: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    recruit_type: Optional[str] = None
    headcount: Optional[int] = None
    experience_years: Optional[str] = None
    education_requirement: Optional[str] = None
    salary_range: Optional[str] = None
    summary: Optional[str] = None
    responsibilities: Optional[list[str]] = None
    requirements: Optional[list[str]] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    compliance_check: Optional[dict[str, Any]] = None
    template_id: Optional[str] = None
    created_by: Optional[str] = None
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
