export const STATUS_LABELS: Record<string, string> = {
  PENDING: 'Chưa bắt đầu', QUEUED: 'Đang xếp hàng', RUNNING: 'Đang thực hiện',
  WAITING_APPROVAL: 'Chờ duyệt kế hoạch', WAITING_USER_DATA: 'Chờ dữ liệu của bạn',
  COMPLETED: 'Đã hoàn thành', NEEDS_REVIEW: 'Cần kiểm tra', PARTIAL: 'Kết quả một phần',
  FAILED: 'Gặp lỗi', CANCELLED: 'Đã hủy', SUCCESS: 'Đã xong', UNKNOWN: 'Chưa xác định',
  PLANNING: 'Đang lập kế hoạch', RESEARCHING: 'Đang tìm nguồn', INDEXING: 'Đang xử lý tài liệu',
  ANALYZING: 'Đang phân tích', WRITING: 'Đang viết', REVIEWING: 'Đang phản biện',
  FINALIZING: 'Đang hoàn thiện', RETRYING: 'Đang thử lại',
};

export const STAGES = [
  { key: 'SUPERVISOR', name: 'Lập kế hoạch', agent: 'Supervisor', description: 'Xác định hướng nghiên cứu và các câu hỏi tìm nguồn.' },
  { key: 'RESEARCHER', name: 'Tìm nguồn', agent: 'Researcher', description: 'Tìm và thu thập các nguồn cho câu hỏi nghiên cứu.' },
  { key: 'CURATOR', name: 'Xử lý tài liệu', agent: 'Curator', description: 'Làm sạch, chia đoạn và lập chỉ mục tài liệu để tra cứu.' },
  { key: 'ANALYST', name: 'Phân tích bằng chứng', agent: 'Analyst', description: 'Đối chiếu luận điểm với các đoạn nguồn đã thu thập.' },
  { key: 'METHODOLOGIST', name: 'Thiết kế phương pháp', agent: 'Methodologist', description: 'Đề xuất giả thuyết, phương pháp và quy trình thu thập dữ liệu.' },
  { key: 'EXPERIMENT_RUNNER', name: 'Chạy phân tích', agent: 'ExperimentRunner', description: 'Thực hiện routine được cho phép và kiểm tra khả năng chạy lại.' },
  { key: 'WRITER', name: 'Soạn bài báo', agent: 'Writer', description: 'Tổng hợp bằng chứng và kết quả thành bản thảo có cấu trúc.' },
  { key: 'CRITIC', name: 'Phản biện bản thảo', agent: 'Critic', description: 'Kiểm tra nội dung, phương pháp và mức hỗ trợ của bằng chứng.' },
  { key: 'POST_PROCESSOR', name: 'Kiểm tra trích dẫn', agent: 'PostProcessor', description: 'Kiểm tra liên kết nguồn và hoàn thiện bản thảo.' },
];

export function stageKey(step: string | null | undefined): string {
  if (step === 'Waiting for dataset') return 'METHODOLOGIST';
  const normalized = (step || '').replace(/[^a-z]/gi, '').toLowerCase();
  return STAGES.find(stage => stage.key.replace(/_/g, '').toLowerCase() === normalized
    || stage.agent.toLowerCase() === normalized)?.key || '';
}

export function stagesFor(type?: string) {
  return STAGES.filter(stage => (type !== 'REVIEW' || !['METHODOLOGIST', 'EXPERIMENT_RUNNER'].includes(stage.key))
    && (type !== 'EMPIRICAL_HUMAN' || stage.key !== 'EXPERIMENT_RUNNER'));
}

export function activityStage(agent: string) { return STAGES.find(stage => stage.agent === agent); }
export function currentStage(step?: string | null) { return STAGES.find(stage => stage.key === stageKey(step)); }
export function statusLabel(status: string) { return STATUS_LABELS[status] || 'Trạng thái chưa xác định'; }

const OUTPUT_LABELS: Record<string, string> = {
  queries_count: 'Truy vấn', sections_count: 'Mục dự kiến', sources_scraped: 'Nguồn đã đọc',
  visited_urls: 'URL đã thu thập', chunks_indexed: 'Đoạn đã lập chỉ mục', verified_claims_count: 'Luận điểm có bằng chứng',
  draft_words: 'Từ bản thảo', feedback_count: 'Góp ý', missing_areas_count: 'Phần còn thiếu',
  citations_count: 'Trích dẫn', report_words: 'Từ báo cáo', budget_limited: 'Chạm giới hạn',
  verdict: 'Kết luận', repeatability: 'Kiểm tra chạy lại',
};
const VERDICT_LABELS: Record<string, string> = {
  PASS: 'Đạt', PASSED: 'Đạt', FAILED: 'Chưa đạt', NOT_RUN: 'Chưa chạy', REVISE: 'Cần sửa',
  NEED_MORE_DATA: 'Cần thêm bằng chứng', NEEDS_REVIEW: 'Cần kiểm tra', IMPROVEMENT: 'Cải thiện so với baseline',
  NO_IMPROVEMENT: 'Không cải thiện so với baseline', INCONCLUSIVE: 'Chưa đủ cơ sở kết luận',
};
export function outputLabel(key: string, value: number | string | boolean) {
  return `${OUTPUT_LABELS[key] || key}: ${typeof value === 'boolean' ? (value ? 'Có' : 'Không') : VERDICT_LABELS[String(value)] || value}`;
}
