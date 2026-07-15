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
  candidate_status: CandidateStatus;
  // Stage 3 扩展：标签 / 来源 / 去重
  tags?: string[];
  source?: string;
  dedup_status?: DedupStatus;
  duplicate_of_resume_id?: string;
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


// ===== Stage 3: 候选人状态流转 =====
export type CandidateStatus =
  | 'NEW'
  | 'SCREENING_PASSED'
  | 'SCREENING_REJECTED'
  | 'INTERVIEWING'
  | 'OFFERED'
  | 'ARCHIVED';

export interface CandidateStatusInfo {
  value: CandidateStatus;
  label: string;
  color: string;
  is_terminal: boolean;
}

export interface CandidateStatusMeta {
  current: CandidateStatus;
  available_transitions: CandidateStatus[];
  all_statuses: CandidateStatusInfo[];
  transitions_map: Record<string, CandidateStatus[]>;
}

export interface CandidateStatusHistoryItem {
  history_id: string;
  resume_id: string;
  from_status: CandidateStatus | null;
  to_status: CandidateStatus;
  reason?: string;
  operator?: string;
  occurred_at: string;
  created_at: string;
}

export interface CandidateStatusHistoryResponse {
  items: CandidateStatusHistoryItem[];
  total: number;
}

export interface CandidateStatusUpdateData {
  to_status: CandidateStatus;
  reason?: string;
  operator?: string;
}

export const CANDIDATE_STATUS_LABEL: Record<CandidateStatus, string> = {
  NEW: '新简历',
  SCREENING_PASSED: '初筛通过',
  SCREENING_REJECTED: '初筛淘汰',
  INTERVIEWING: '面试中',
  OFFERED: '已录用',
  ARCHIVED: '已归档',
};

export const CANDIDATE_STATUS_COLOR: Record<CandidateStatus, string> = {
  NEW: 'default',
  SCREENING_PASSED: 'blue',
  SCREENING_REJECTED: 'warning',
  INTERVIEWING: 'processing',
  OFFERED: 'success',
  ARCHIVED: 'default',
};

// ---------------------------------------------------------------------------
// Stage 3 扩展：去重 / 标签 / 备注 / 评价
// ---------------------------------------------------------------------------

export type DedupStatus = "NONE" | "SUSPECTED" | "CONFIRMED_DUP" | "IGNORED";

export const DEDUP_STATUS_LABEL: Record<DedupStatus, string> = {
  NONE: "正常",
  SUSPECTED: "疑似重复",
  CONFIRMED_DUP: "已确认重复",
  IGNORED: "已忽略",
};

export const DEDUP_STATUS_COLOR: Record<DedupStatus, string> = {
  NONE: "default",
  SUSPECTED: "warning",
  CONFIRMED_DUP: "error",
  IGNORED: "default",
};

export type CandidateNoteType = "NOTE" | "EVALUATION";

export const NOTE_TYPE_LABEL: Record<CandidateNoteType, string> = {
  NOTE: "备注",
  EVALUATION: "评价",
};

export const NOTE_TYPE_COLOR: Record<CandidateNoteType, string> = {
  NOTE: "default",
  EVALUATION: "gold",
};

export interface CandidateNoteItem {
  note_id: string;
  resume_id: string;
  note_type: CandidateNoteType;
  content: string;
  rating?: number | null;
  author?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateNoteListResponse {
  items: CandidateNoteItem[];
  total: number;
}

export interface CandidateNoteCreateData {
  note_type?: CandidateNoteType;
  content: string;
  rating?: number;
  author?: string;
}

export interface CandidateNoteUpdateData {
  content?: string;
  rating?: number;
}

export interface TagsMetaResponse {
  tags: string[];
  sources: string[];
}

export interface ResumeListParams {
  page?: number;
  page_size?: number;
  parse_status?: ResumeParseStatus;
  candidate_status?: CandidateStatus;
  keyword?: string;
  tag?: string;
  source?: string;
  dedup_status?: DedupStatus;
  date_from?: string;
  date_to?: string;
}
