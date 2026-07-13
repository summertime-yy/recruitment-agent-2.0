/// <reference types="vite/client" />

export interface ApiResponse<T> {
  success: true;
  data: T;
  message?: string;
  request_id: string;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: any;
  };
  request_id: string;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
  keyword?: string;
  status?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type JDStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export interface JD {
  jd_id: string;
  title: string;
  department?: string;
  level?: string;
  location?: string;
  job_type?: string;
  recruit_type?: string;
  headcount?: number;
  experience_years?: string;
  education_requirement?: string;
  salary_range?: string;
  summary?: string;
  responsibilities?: string[];
  requirements?: string[];
  required_skills?: string[];
  preferred_skills?: string[];
  compliance_check?: {
    passed: boolean;
    issues: string[];
  };
  template_id?: string;
  created_by?: string;
  status: JDStatus;
  created_at: string;
  updated_at: string;
}

export interface JDGenerateFormData {
  title: string;
  department?: string;
  level?: string;
  location?: string;
  job_type?: string;
  recruit_type?: string;
  headcount?: number;
  experience_years?: string;
  education_requirement?: string;
  salary_range?: string;
  description: string;
  required_skills?: string[];
  preferred_skills?: string[];
}

export interface JDGenerateRequest extends JDGenerateFormData {
  requirements?: string[];
  template_id?: string;
}

export interface JDGenerateResponse {
  jd: JD;
  skill_execution_id: number;
  execution_time_ms: number;
  validation_score: number;
}

export type ResumeParseStatus = 'PENDING' | 'PARSING' | 'PARSED' | 'FAILED';

export interface EducationItem {
  school: string;
  degree: string;
  major: string;
  start_date?: string;
  end_date?: string;
}

export interface WorkExperienceItem {
  company: string;
  position: string;
  start_date?: string;
  end_date?: string;
  description?: string;
}

export interface ProjectExperienceItem {
  name: string;
  role?: string;
  start_date?: string;
  end_date?: string;
  description?: string;
}

export interface ParsedContent {
  summary?: string;
  education: EducationItem[];
  work_experience: WorkExperienceItem[];
  project_experience: ProjectExperienceItem[];
  skills: string[];
}

export interface Resume {
  resume_id: string;
  candidate_name?: string;
  file_name: string;
  file_size?: number;
  file_type: string;
  phone?: string;
  email?: string;
  parsed_content?: ParsedContent;
  parse_status: ResumeParseStatus;
  parse_error?: string;
  parsing_skill_version?: string;
  parse_time_ms?: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ResumeUploadResponse {
  resume_id: string;
  file_name: string;
  file_size?: number;
  file_type: string;
  parse_status: ResumeParseStatus;
  created_at: string;
}
