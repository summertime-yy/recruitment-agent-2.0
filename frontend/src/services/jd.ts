import request from '@/utils/request';
import type {
  JD,
  JDGenerateRequest,
  JDGenerateResponse,
  PaginationParams,
  PaginatedResponse,
} from '@/types';

export const jdApi = {
  generate: (data: JDGenerateRequest) =>
    request.post<any, JDGenerateResponse>('/jds/generate', data),

  list: (params?: PaginationParams & { department?: string; level?: string }) =>
    request.get<any, PaginatedResponse<JD>>('/jds', { params }),

  getById: (jdId: string) =>
    request.get<any, JD>(`/jds/${jdId}`),

  update: (jdId: string, data: Partial<Omit<JD, 'jd_id' | 'created_at' | 'updated_at'>>) =>
    request.put<any, JD>(`/jds/${jdId}`, data),

  delete: (jdId: string) =>
    request.delete<any, { message: string }>(`/jds/${jdId}`),
};
