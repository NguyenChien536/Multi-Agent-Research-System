export interface BudgetConfig {
  max_cost_usd?: number;
  max_llm_calls?: number;
  max_input_tokens?: number;
  max_output_tokens?: number;
  timeout_seconds?: number;
}

export interface ResearchTaskCreate {
  title: string;
  research_question: string;
  description?: string;
  research_depth?: "SHALLOW" | "STANDARD" | "DEEP";
  language?: string;
  require_plan_approval?: boolean;
  max_sources?: number;
  max_iterations?: number;
  report_length?: "SHORT" | "MEDIUM" | "LONG";
  citation_style?: "IEEE" | "APA" | "HARVARD";
  budget?: BudgetConfig;
}

export interface ResearchTaskResponse {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  research_question: string;
  research_depth: string;
  language: string;
  status: string; // PENDING, QUEUED, PLANNING, WAITING_APPROVAL, RESEARCHING, etc.
  require_plan_approval: boolean;
  max_sources: number;
  max_iterations: number;
  current_iteration: number;
  attempt_number: number;
  total_cost_usd: number;
  total_tokens_used: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface ApiError {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  full_name?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
}

export interface ResearchReportResponse {
  id: string;
  research_task_id: string;
  title: string;
  content_markdown: string;
  executive_summary?: string | null;
  word_count: number;
  created_at: string;
  updated_at: string;
}
