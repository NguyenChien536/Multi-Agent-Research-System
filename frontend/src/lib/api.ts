import { ResearchTaskCreate, ResearchTaskResponse, ApiError, ResearchReportResponse, CitationResponse, ResearchSourceResponse, AgentRunResponse, ArtifactItemResponse, PdfUploadResponse, PlanReviewResponse, PlanApprovalRequest, PlanRejectRequest, UserDataResumeRequest, ProtocolResponse, AnalysisRunResponse, ExperimentJournalEntryResponse, DatasetUploadResponse, TokenResponse, UserCreate, UserResponse } from '../types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export class APIError extends Error {
  constructor(public status: number, public data: ApiError) {
    super(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
    this.name = 'APIError';
  }
}

const TOKEN_KEY = 'synthia_access_token';

function getAccessToken(): string | null {
  return typeof window === 'undefined' ? null : window.sessionStorage.getItem(TOKEN_KEY);
}

function setAccessToken(token: string): void {
  window.sessionStorage.setItem(TOKEN_KEY, token);
}

function clearAccessToken(): void {
  if (typeof window !== 'undefined') window.sessionStorage.removeItem(TOKEN_KEY);
}

async function fetcher<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers = new Headers(options?.headers);
  if (options?.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = getAccessToken();
  const isPublicAuth = endpoint === '/auth/login' || endpoint === '/auth/register';
  if (token && !isPublicAuth) headers.set('Authorization', `Bearer ${token}`);

  const config: RequestInit = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401 && !isPublicAuth) {
        clearAccessToken();
        if (typeof window !== 'undefined') {
          const next = `${window.location.pathname}${window.location.search}`;
          window.location.assign(`/login?next=${encodeURIComponent(next)}`);
        }
      }
      throw new APIError(response.status, data || { detail: 'Unknown error occurred' });
    }

    return data as T;
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    throw new Error('Network error or API is unreachable');
  }
}

export const api = {
  auth: {
    hasSession: () => Boolean(getAccessToken()),
    logout: clearAccessToken,
    register: (data: UserCreate) => fetcher<UserResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    login: async (email: string, password: string) => {
      const token = await fetcher<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setAccessToken(token.access_token);
      return token;
    },
    me: () => fetcher<UserResponse>('/auth/me'),
  },
  tasks: {
    create: (data: ResearchTaskCreate) =>
      fetcher<ResearchTaskResponse>('/research', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    list: (skip = 0, limit = 20) =>
      fetcher<ResearchTaskResponse[]>(`/research?skip=${skip}&limit=${limit}`),

    get: (id: string) =>
      fetcher<ResearchTaskResponse>(`/research/${id}`),

    start: (id: string) =>
      fetcher<{ status: string; message: string; task_id: string }>(`/research/${id}/start`, {
        method: 'POST',
      }),

    getReport: (id: string) =>
      fetcher<ResearchReportResponse>(`/research/${id}/report`),

    getCitations: (id: string) =>
      fetcher<CitationResponse[]>(`/research/${id}/citations`),

    getSources: (id: string) =>
      fetcher<ResearchSourceResponse[]>(`/research/${id}/sources`),

    getAgentRuns: (id: string) =>
      fetcher<AgentRunResponse[]>(`/research/${id}/agent-runs`),

    cancel: (id: string) =>
      fetcher<{ status: string; message: string; task_id: string }>(`/research/${id}/cancel`, {
        method: 'POST',
      }),

    delete: (id: string) =>
      fetcher<{ message: string; task_id: string }>(`/research/${id}`, {
        method: 'DELETE',
      }),

    uploadPdf: async (id: string, file: File): Promise<PdfUploadResponse> => {
      const formData = new FormData();
      formData.append('file', file);
      const url = `${API_BASE_URL}/research/${id}/upload`;
      const token = getAccessToken();
      const headers = new Headers();
      if (token) headers.set('Authorization', `Bearer ${token}`);
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: formData,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new APIError(response.status, data || { detail: 'Upload failed' });
      }
      return data as PdfUploadResponse;
    },

    getArtifacts: (id: string) =>
      fetcher<ArtifactItemResponse[]>(`/research/${id}/artifacts`),

    getArtifactDownloadUrl: (taskId: string, artifactId: string) =>
      `${API_BASE_URL}/research/${taskId}/artifacts/${artifactId}/download`,

    getPlan: (id: string) =>
      fetcher<PlanReviewResponse>(`/research/${id}/plan`),

    approvePlan: (id: string, payload: PlanApprovalRequest) =>
      fetcher<ResearchTaskResponse>(`/research/${id}/plan/approve`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),

    rejectPlan: (id: string, payload: PlanRejectRequest) =>
      fetcher<ResearchTaskResponse>(`/research/${id}/plan/reject`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),

    getProtocol: (id: string) =>
      fetcher<ProtocolResponse>(`/research/${id}/protocol`),

    resumeWithData: (id: string, payload: UserDataResumeRequest) =>
      fetcher<ResearchTaskResponse>(`/research/${id}/data/resume`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),

    uploadFieldworkResult: (id: string, file: File) => {
      const body = new FormData();
      body.append('file', file);
      return fetcher<{ artifact_id: string; file_name: string; sha256_hash: string }>(
        `/research/${id}/data/files`, { method: 'POST', body },
      );
    },

    getExperiments: (id: string) =>
      fetcher<AnalysisRunResponse[]>(`/research/${id}/experiments`),

    getJournal: (id: string) =>
      fetcher<ExperimentJournalEntryResponse[]>(`/research/${id}/journal`),

    uploadDataset: async (id: string, file: File) => {
      const token = getAccessToken();
      const headers = new Headers();
      if (token) headers.set('Authorization', `Bearer ${token}`);

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE_URL}/research/${id}/dataset`, {
        method: 'POST',
        headers,
        body: formData,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new APIError(response.status, data || { detail: 'Upload dataset failed' });
      }
      return data as DatasetUploadResponse;
    },
  }
};


