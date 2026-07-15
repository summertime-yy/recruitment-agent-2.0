import request from '@/utils/request';
import type { Resume, ResumeUploadResponse, PaginatedResponse, ParsedContent, TagsMetaResponse, DedupStatus, CandidateStatus, ResumeParseStatus } from '@/types';

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

export interface ResumeUpdateData {
  candidate_name?: string;
  phone?: string;
  email?: string;
  parsed_content?: ParsedContent;
  tags?: string[];
  source?: string;
}

export const resumeApi = {
  upload(file: File, autoParse = true): Promise<ResumeUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return request.post('/resumes/upload', formData, {
      params: { auto_parse: autoParse },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  parse(resumeId: string): Promise<Resume> {
    return request.post(`/resumes/${resumeId}/parse`);
  },

  list(params: ResumeListParams = {}): Promise<PaginatedResponse<Resume>> {
    return request.get('/resumes', { params });
  },

  getById(resumeId: string): Promise<Resume> {
    return request.get(`/resumes/${resumeId}`);
  },

  update(resumeId: string, data: ResumeUpdateData): Promise<Resume> {
    return request.put(`/resumes/${resumeId}`, data);
  },

  delete(resumeId: string): Promise<{ message: string }> {
    return request.delete(`/resumes/${resumeId}`);
  },

  getPreviewUrl(resumeId: string): string {
    return `/api/v1/resumes/${resumeId}/preview`;
  },

  /** 获取所有已用标签与来源（用于筛选下拉） */
  getTagsMeta(): Promise<TagsMetaResponse> {
    return request.get('/resumes/tags/meta');
  },

  /** 处理疑似重复：CONFIRM_DUP / IGNORE / RECHECK */
  handleDedup(resumeId: string, action: 'CONFIRM_DUP' | 'IGNORE' | 'RECHECK'): Promise<Resume> {
    return request.post(`/resumes/${resumeId}/dedup`, { action });
  },
};

