import request from '@/utils/request';
import type { Resume, ResumeUploadResponse, PaginatedResponse, ParsedContent } from '@/types';

export interface ResumeListParams {
  page?: number;
  page_size?: number;
  parse_status?: string;
  keyword?: string;
}

export interface ResumeUpdateData {
  candidate_name?: string;
  phone?: string;
  email?: string;
  parsed_content?: ParsedContent;
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
};
