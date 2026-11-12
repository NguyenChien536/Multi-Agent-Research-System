export interface ReportRevision {
  id: string;
  request_id: string;
  base_version_id: string;
  instructions: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'NEEDS_REVIEW' | 'FAILED' | 'CANCELLED';
  workflow_run_id: string | null;
  result_version_id: string | null;
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
}

export function revisionActive(item: ReportRevision): boolean {
  return item.status === 'QUEUED' || item.status === 'RUNNING';
}

export function normalizeCitationLabel(label: string): string {
  const value = label.trim();
  return /^\d+$/.test(value) ? `[${value}]` : value;
}

export function revisionStatus(item: ReportRevision): string {
  const labels: Record<ReportRevision['status'], string> = {
    QUEUED: 'Đang chờ xử lý', RUNNING: 'Đang sửa và kiểm tra', COMPLETED: 'Đã tạo phiên bản mới',
    NEEDS_REVIEW: 'Đã tạo bản mới — cần rà soát', FAILED: 'Không hoàn tất', CANCELLED: 'Đã hủy',
  };
  if (item.error_code === 'BUDGET_LIMIT') return 'Đã chạm giới hạn ngân sách';
  return labels[item.status] || item.status;
}
