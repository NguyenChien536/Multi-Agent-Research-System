export interface BudgetConfig {
  max_cost_usd?: number;
  max_llm_calls?: number;
  max_input_tokens?: number;
  max_output_tokens?: number;
  timeout_seconds?: number;
}

export type ResearchType = "REVIEW" | "EMPIRICAL_COMPUTATIONAL" | "EMPIRICAL_HUMAN";

export interface ResearchTaskCreate {
  title: string;
  research_question: string;
  description?: string;
  research_type?: ResearchType;
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
  research_type?: ResearchType;
  research_depth: string;
  language: string;
  status: string; // PENDING, QUEUED, PLANNING, WAITING_APPROVAL, WAITING_USER_DATA, RESEARCHING, etc.
  current_step?: string | null;
  require_plan_approval: boolean;
  max_sources: number;
  max_iterations: number;
  current_iteration: number;
  attempt_number: number;
  report_length?: string;
  citation_style?: string;
  total_cost_usd: number;
  total_tokens_used: number;
  plan?: {
    research_angle?: string;
    search_queries?: string[];
    required_sections?: string[];
    [key: string]: any;
  } | null;
  plan_approved?: boolean;
  plan_feedback?: string | null;
  protocol_artifact_id?: string | null;
  user_data_submission?: Record<string, any> | null;
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

export interface CitationResponse {
  id: string;
  citation_number?: number | null;
  citation_label: string;
  claim_text?: string | null;
  source_id: string;
  source_title?: string | null;
  source_url: string;
  chunk_id?: string | null;
  chunk_content?: string | null;
}

export interface ResearchSourceResponse {
  id: string;
  source_tag: string;
  title?: string | null;
  url: string;
  source_type: string;
  author?: string | null;
  publication_date?: string | null;
  content_snippet?: string | null;
  summary?: string | null;
  relevance_score: number;
  attribution?: string | null;
  provider_name?: string | null;
  license_name?: string | null;
  created_at: string;
}

export interface AgentRunResponse {
  id: string;
  research_task_id: string;
  agent_name: string;
  status: string;
  iteration: number;
  attempt_number: number;
  model?: string | null;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  input_summary: Record<string, any>;
  output_summary: Record<string, any>;
  tool_calls: Array<Record<string, any>>;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface ArtifactItemResponse {
  id: string;
  research_task_id: string;
  export_type: string;
  file_path: string;
  file_size_bytes: number;
  download_url?: string | null;
  created_at: string;
}

export interface PdfUploadResponse {
  artifact_id: string;
  source_id: string;
  source_tag: string;
  file_name: string;
  file_size_bytes: number;
  page_count: number;
  chunks_count: number;
  sha256_hash: string;
  message: string;
}

export interface PlanReviewResponse {
  task_id: string;
  status: string;
  require_plan_approval: boolean;
  plan_approved: boolean;
  plan?: {
    research_angle?: string;
    search_queries?: string[];
    required_sections?: string[];
    [key: string]: any;
  } | null;
  plan_feedback?: string | null;
}

export interface PlanApprovalRequest {
  approved_queries?: string[];
  feedback?: string;
}

export interface PlanRejectRequest {
  reason?: string;
}

export interface UserDataResumeRequest {
  sample_size: number;
  method_notes: string;
  results_summary: string;
  data_provenance?: string;
  file_artifact_id?: string;
}

export interface ProtocolResponse {
  task_id: string;
  research_type: string;
  status: string;
  protocol_artifact_id?: string | null;
  download_url?: string | null;
  content_markdown?: string | null;
}

export interface AnalysisRunResponse {
  id: string;
  research_task_id: string;
  routine_name: string;
  status: string;
  dataset_artifact_id?: string | null;
  input_checksum?: string | null;
  manifest: {
    manifest_version?: string;
    routine_name?: string;
    routine_version?: string;
    input_checksum?: string;
    dataset_rows?: number;
    valid_rows?: number;
    train_rows?: number;
    test_rows?: number;
    target_column?: string;
    feature_columns?: string[];
    parameters?: Record<string, any>;
    [key: string]: any;
  };
  metrics?: {
    baseline?: {
      model_type?: string;
      mae?: number;
      rmse?: number;
      r2?: number;
    };
    model?: {
      model_type?: string;
      alpha?: number;
      mae?: number;
      rmse?: number;
      r2?: number;
    };
    comparison?: {
      primary_metric?: string;
      delta_mae?: number;
      delta_rmse?: number;
      verdict?: 'IMPROVEMENT' | 'NO_IMPROVEMENT' | string;
      pct_improvement?: number;
    };
    coefficients?: Record<string, number>;
    intercept?: number;
    [key: string]: any;
  } | null;
  reproducibility_status: 'NOT_RUN' | 'PASSED' | 'FAILED' | string;
  reproducibility_diff?: {
    diff_mae?: number;
    diff_rmse?: number;
    diff_r2?: number;
    tolerance?: number;
    status?: string;
    [key: string]: any;
  } | null;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface ExperimentJournalEntryResponse {
  id: string;
  research_task_id: string;
  analysis_run_id: string;
  sequence: number;
  kind: string;
  actor: string;
  payload: Record<string, any>;
  artifact_ids: string[];
  created_at: string;
}

export interface DatasetUploadResponse {
  artifact_id: string;
  file_name: string;
  rows_count: number;
  columns_count: number;
  columns: string[];
  checksum: string;
}

