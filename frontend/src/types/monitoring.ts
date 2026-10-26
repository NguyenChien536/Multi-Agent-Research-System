export interface MonitorActivity {
  id: string;
  agent: string;
  status: string;
  iteration: number;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
  output: Record<string, number | string | boolean>;
  has_error: boolean;
}

export interface ResearchMonitor {
  task_id: string;
  title: string;
  research_type: string;
  status: string;
  current_step: string | null;
  current_iteration: number;
  attempt_number: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  observed_at: string;
  worker_lease_expired: boolean | null;
  next_action: string;
  workflow: { id: string; run_number: number; status: string; plan_version: number;
    started_at: string; completed_at: string | null } | null;
  counts: Record<string, number>;
  estimated_cost_usd: number;
  reserved_cost_usd: number;
  recorded_tokens: number;
  accounting_source: string;
  activities: MonitorActivity[];
  activity_total: number;
  activity_offset: number;
  activity_limit: number;
}
