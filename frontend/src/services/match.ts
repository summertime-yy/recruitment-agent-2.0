import request from '@/utils/request';
import type {
  MatchScore,
  MatchRankingResponse,
  BatchTaskResponse,
  BatchTaskStatus,
} from '@/types';

export interface MatchOneRequest {
  jd_id: string;
  resume_id: string;
  force?: boolean;
}

export interface BatchMatchRequest {
  jd_id: string;
  resume_ids?: string[];
  limit?: number;
  force?: boolean;
}

export const matchApi = {
  matchOne: (data: MatchOneRequest) =>
    request.post<any, MatchScore>('/match-scores', data),

  batchMatch: (data: BatchMatchRequest) =>
    request.post<any, BatchTaskResponse>('/match-scores/batch', data),

  getBatchStatus: (taskId: string) =>
    request.get<any, BatchTaskStatus>(`/match-scores/batch/${taskId}`),

  getScore: (scoreId: string) =>
    request.get<any, MatchScore>(`/match-scores/${scoreId}`),

  rankByJd: (jdId: string, params?: { limit?: number; offset?: number }) =>
    request.get<any, MatchRankingResponse>(`/jds/${jdId}/ranking`, { params }),

  listByResume: (resumeId: string, params?: { limit?: number }) =>
    request.get<any, MatchScore[]>(`/resumes/${resumeId}/matches`, { params }),
};
