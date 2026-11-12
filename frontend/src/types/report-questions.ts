export interface ReportVersionMetadata {
  version_id: string;
  version_number: number;
  title: string;
  content_markdown: string;
  review_status: string;
  created_at: string;
}

export interface ReportQuestion {
  id: string;
  report_version_id: string;
  request_id: string;
  question: string;
  status: 'RUNNING' | 'ANSWERED' | 'INSUFFICIENT_EVIDENCE' | 'FAILED' | 'BUDGET_LIMIT';
  answer: string | null;
  references: Array<{ citation_id: string; source_title: string | null; source_url: string; quote: string }>;
  context_truncated: boolean;
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ReportQuestionHistory {
  report_version_id: string;
  version_number: number;
  items: ReportQuestion[];
  total: number;
  offset: number;
  limit: number;
}
