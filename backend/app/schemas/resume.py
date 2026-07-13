from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    school: str = Field(..., description="学校名称")
    degree: str = Field(..., description="学位/学历，如本科、硕士")
    major: str = Field(..., description="专业")
    start_date: Optional[str] = Field(None, description="开始时间，如2018-09")
    end_date: Optional[str] = Field(None, description="结束时间，如2022-06")


class WorkExperienceItem(BaseModel):
    company: str = Field(..., description="公司名称")
    position: str = Field(..., description="职位")
    start_date: Optional[str] = Field(None, description="开始时间")
    end_date: Optional[str] = Field(None, description="结束时间")
    description: Optional[str] = Field(None, description="工作内容描述")


class ProjectExperienceItem(BaseModel):
    name: str = Field(..., description="项目名称")
    role: Optional[str] = Field(None, description="担任角色")
    start_date: Optional[str] = Field(None, description="开始时间")
    end_date: Optional[str] = Field(None, description="结束时间")
    description: Optional[str] = Field(None, description="项目描述")


class ParsedContent(BaseModel):
    summary: Optional[str] = Field(None, description="个人简介/自我评价")
    education: list[EducationItem] = Field(default_factory=list, description="教育经历")
    work_experience: list[WorkExperienceItem] = Field(default_factory=list, description="工作经历")
    project_experience: list[ProjectExperienceItem] = Field(default_factory=list, description="项目经历")
    skills: list[str] = Field(default_factory=list, description="技能标签列表")


class ResumeUploadResponse(BaseModel):
    resume_id: str
    file_name: str
    file_size: Optional[int] = None
    file_type: str
    parse_status: str
    created_at: datetime


class ResumeParseRequest(BaseModel):
    resume_id: str


class ResumeResponse(BaseModel):
    resume_id: str
    candidate_name: Optional[str] = None
    file_name: str
    file_size: Optional[int] = None
    file_type: str
    phone: Optional[str] = None
    email: Optional[str] = None
    parsed_content: Optional[ParsedContent] = None
    parse_status: str
    parse_error: Optional[str] = None
    parsing_skill_version: Optional[str] = None
    parse_time_ms: Optional[int] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    items: list[ResumeResponse]
    total: int
    page: int
    page_size: int


class ResumeUpdateRequest(BaseModel):
    candidate_name: Optional[str] = Field(None, description="候选人姓名")
    phone: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    parsed_content: Optional[ParsedContent] = Field(None, description="结构化内容")
