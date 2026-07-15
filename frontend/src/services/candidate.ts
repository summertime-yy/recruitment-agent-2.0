import request from '@/utils/request';
import type {
  CandidateStatusMeta,
  CandidateStatusHistoryResponse,
  CandidateStatusUpdateData,
  CandidateNoteItem,
  CandidateNoteListResponse,
  CandidateNoteCreateData,
  CandidateNoteUpdateData,
  Resume,
} from '@/types';

export const candidateApi = {
  getStatusMeta(resumeId: string): Promise<CandidateStatusMeta> {
    return request.get(`/candidates/${resumeId}/status/meta`);
  },

  updateStatus(resumeId: string, data: CandidateStatusUpdateData): Promise<Resume> {
    return request.put(`/candidates/${resumeId}/status`, data);
  },

  getStatusHistory(resumeId: string): Promise<CandidateStatusHistoryResponse> {
    return request.get(`/candidates/${resumeId}/status/history`);
  },

  // 备注与评价
  listNotes(resumeId: string): Promise<CandidateNoteListResponse> {
    return request.get(`/candidates/${resumeId}/notes`);
  },

  createNote(resumeId: string, data: CandidateNoteCreateData): Promise<CandidateNoteItem> {
    return request.post(`/candidates/${resumeId}/notes`, data);
  },

  updateNote(resumeId: string, noteId: string, data: CandidateNoteUpdateData): Promise<CandidateNoteItem> {
    return request.put(`/candidates/${resumeId}/notes/${noteId}`, data);
  },

  deleteNote(resumeId: string, noteId: string): Promise<{ message: string }> {
    return request.delete(`/candidates/${resumeId}/notes/${noteId}`);
  },
};

