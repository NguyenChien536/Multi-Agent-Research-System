import { ResearchTaskCreate, ResearchTaskResponse, ApiError, ResearchReportResponse, TokenResponse, UserCreate, UserResponse } from '../types';

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
  if (options?.body) headers.set('Content-Type', 'application/json');
  const token = getAccessToken();
  if (token && !endpoint.startsWith('/auth/')) headers.set('Authorization', `Bearer ${token}`);

  const config: RequestInit = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401 && !endpoint.startsWith('/auth/')) {
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
  }
};
