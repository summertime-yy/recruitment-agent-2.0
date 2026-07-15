from datetime import datetime

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    school: str = Field(..., description="学校名称")
    degree: str = Field(..., description="学位/学历，如本科、硕士")
    major: str = Field(..., description="专业")
    start_date: str | None = Field(None, description="开始时间，如2018-09")
    end_date: str | None = Field(None, description="结束时间，如2022-06")


class WorkExperienceItem(BaseModel):
    company: str = Field(..., description="公司名称")
    position: str = Field(..., description="职位")
    start_date: str | None = Field(None, description="开始时间")
    end_date: str | None = Field(None, description="结束时间")
    description: str | None = Field(None, description="工作内容描述")


class ProjectExperienceItem(BaseModel):
    name: str = Field(..., description="项目名称")
    role: str | None = Field(None, description="担任角色")
    start_date: str | None = Field(None, description="开始时间")
    end_date: str | None = Field(None, description="结束时间")
    description: str | None = Field(None, description="项目描述")


class ParsedContent(BaseModel):
    summary: str | None = Field(None, description="个人简介/自我评价")
    education: list[EducationItem] = Field(default_factory=list, description="教育经历")
    work_experience: list[WorkExperienceItem] = Field(default_factory=list, description="工作经历")
    project_experience: list[ProjectExperienceItem] = Field(default_factory=list, description="项目经历")
    skills: list[str] = Field(default_factory=list, description="技能标签列表")


class ResumeUploadResponse(BaseModel):
    resume_id: str
    file_name: str
    file_size: int | None = None
    file_type: str
    parse_status: str
    created_at: datetime


class ResumeParseRequest(BaseModel):
    resume_id: str


class ResumeResponse(BaseModel):
    resume_id: str
    candidate_name: str | None = None
    file_name: str
    file_size: int | None = None
    file_type: str
    phone: str | None = None
    email: str | None = None
    parsed_content: ParsedContent | None = None
    parse_status: str
    parse_error: str | None = None
    parsing_skill_version: str | None = None
    parse_time_ms: int | None = None
    created_by: str | None = None
    candidate_status: str = "NEW"
    # ---- Stage 3 扩展：标签 / 来源 / 去重 ----
    tags: list[str] | None = None
    source: str | None = None
    dedup_status: str = "NONE"
    duplicate_of_resume_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    items: list[ResumeResponse]
    total: int
    page: int
    page_size: int


class ResumeUpdateRequest(BaseModel):
    candidate_name: str | None = Field(None, description="候选人姓名")
    phone: str | None = Field(None, description="手机号")
    email: str | None = Field(None, description="邮箱")
    parsed_content: ParsedContent | None = Field(None, description="结构化内容")
    tags: list[str] | None = Field(None, description="候选人标签列表")
    source: str | None = Field(None, description="来源渠道")


class ResumeDedupActionRequest(BaseModel):
    """去重状态人工处理：确认重复 / 忽略 / 重新检测。"""

    action: str = Field(..., description="CONFIRM_DUP / IGNORE / RECHECK")
