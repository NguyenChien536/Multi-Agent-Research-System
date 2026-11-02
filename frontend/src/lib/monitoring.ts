export const STATUS_LABELS_VI: Record<string, string> = {
  PENDING: 'Chưa bắt đầu', QUEUED: 'Đang xếp hàng', RUNNING: 'Đang thực hiện',
  WAITING_APPROVAL: 'Chờ duyệt kế hoạch', WAITING_USER_DATA: 'Chờ dữ liệu thực địa',
  COMPLETED: 'Đã hoàn thành', NEEDS_REVIEW: 'Cần xem xét', PARTIAL: 'Kết quả một phần',
  FAILED: 'Thất bại', CANCELLED: 'Đã dừng', SUCCESS: 'Đã xong', UNKNOWN: 'Chưa xác định',
  PLANNING: 'Đang lập kế hoạch', RESEARCHING: 'Đang tìm nguồn', INDEXING: 'Đang xử lý tài liệu',
  ANALYZING: 'Đang phân tích', WRITING: 'Đang soạn thảo', REVIEWING: 'Đang phản biện',
  FINALIZING: 'Đang hoàn thiện', RETRYING: 'Đang thử lại',
};

export const STATUS_LABELS_EN: Record<string, string> = {
  PENDING: 'Pending', QUEUED: 'Queued', RUNNING: 'In Progress',
  WAITING_APPROVAL: 'Awaiting Plan Approval', WAITING_USER_DATA: 'Awaiting Data (Gate G4)',
  COMPLETED: 'Completed', NEEDS_REVIEW: 'Needs Review', PARTIAL: 'Partial Result',
  FAILED: 'Failed', CANCELLED: 'Cancelled', SUCCESS: 'Finished', UNKNOWN: 'Unknown',
  PLANNING: 'Planning', RESEARCHING: 'Searching Sources', INDEXING: 'Processing Sources',
  ANALYZING: 'Analyzing Evidence', WRITING: 'Drafting Report', REVIEWING: 'Reviewing Draft',
  FINALIZING: 'Finalizing', RETRYING: 'Retrying',
};

export const STATUS_LABELS = STATUS_LABELS_VI;

export const STAGES = [
  { key: 'SUPERVISOR', name: 'Lập kế hoạch', name_en: 'Planning', agent: 'Supervisor', description: 'Xác định hướng nghiên cứu và các câu hỏi tìm nguồn.', description_en: 'Defines research scope and key search queries.' },
  { key: 'RESEARCHER', name: 'Tìm nguồn', name_en: 'Literature Search', agent: 'Researcher', description: 'Tìm và thu thập các nguồn cho câu hỏi nghiên cứu.', description_en: 'Discovers and retrieves relevant scientific literature.' },
  { key: 'CURATOR', name: 'Xử lý tài liệu', name_en: 'Source Processing', agent: 'Curator', description: 'Làm sạch, chia đoạn và lập chỉ mục tài liệu để tra cứu.', description_en: 'Cleans, chunks, and indexes documents for retrieval.' },
  { key: 'ANALYST', name: 'Phân tích bằng chứng', name_en: 'Evidence Analysis', agent: 'Analyst', description: 'Đối chiếu luận điểm với các đoạn nguồn đã thu thập.', description_en: 'Cross-verifies claims against retrieved source chunks.' },
  { key: 'METHODOLOGIST', name: 'Thiết kế phương pháp', name_en: 'Methodology Design', agent: 'Methodologist', description: 'Đề xuất giả thuyết, phương pháp và quy trình thu thập dữ liệu.', description_en: 'Designs protocols, hypotheses, and data schemas.' },
  { key: 'EXPERIMENT_RUNNER', name: 'Chạy phân tích', name_en: 'Execution & Analysis', agent: 'ExperimentRunner', description: 'Thực hiện routine được cho phép và kiểm tra khả năng chạy lại.', description_en: 'Executes verified computational routines and checks repeatability.' },
  { key: 'WRITER', name: 'Soạn bài báo', name_en: 'Drafting Paper', agent: 'Writer', description: 'Tổng hợp bằng chứng và kết quả thành bản thảo có cấu trúc.', description_en: 'Synthesizes verified claims into a cohesive academic draft.' },
  { key: 'CRITIC', name: 'Phản biện bản thảo', name_en: 'Peer Review', agent: 'Critic', description: 'Kiểm tra nội dung, phương pháp và mức hỗ trợ của bằng chứng.', description_en: 'Evaluates methodological rigor and citation support.' },
  { key: 'POST_PROCESSOR', name: 'Kiểm tra trích dẫn', name_en: 'Citation Check', agent: 'PostProcessor', description: 'Kiểm tra liên kết nguồn và hoàn thiện bản thảo.', description_en: 'Validates source links and polishes paper formatting.' },
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
export function statusLabel(status: string, lang: 'en' | 'vi' = 'en') {
  if (lang === 'vi') return STATUS_LABELS_VI[status] || 'Trạng thái chưa xác định';
  return STATUS_LABELS_EN[status] || 'Unknown status';
}

const OUTPUT_LABELS_VI: Record<string, string> = {
  queries_count: 'Truy vấn', sections_count: 'Mục dự kiến', sources_scraped: 'Nguồn đã đọc',
  visited_urls: 'URL đã thu thập', chunks_indexed: 'Đoạn đã lập chỉ mục', verified_claims_count: 'Luận điểm có bằng chứng',
  draft_words: 'Từ bản thảo', feedback_count: 'Góp ý', missing_areas_count: 'Phần còn thiếu',
  citations_count: 'Trích dẫn', report_words: 'Từ báo cáo', budget_limited: 'Chạm giới hạn',
  verdict: 'Kết luận', repeatability: 'Kiểm tra chạy lại',
};

const OUTPUT_LABELS_EN: Record<string, string> = {
  queries_count: 'Queries', sections_count: 'Sections planned', sources_scraped: 'Sources read',
  visited_urls: 'URLs retrieved', chunks_indexed: 'Chunks indexed', verified_claims_count: 'Verified claims',
  draft_words: 'Draft words', feedback_count: 'Critique notes', missing_areas_count: 'Gaps identified',
  citations_count: 'Citations', report_words: 'Report words', budget_limited: 'Budget ceiling reached',
  verdict: 'Verdict', repeatability: 'Repeatability check',
};

const VERDICT_LABELS_VI: Record<string, string> = {
  PASS: 'Đạt', PASSED: 'Đạt', FAILED: 'Chưa đạt', NOT_RUN: 'Chưa chạy', REVISE: 'Cần sửa',
  NEED_MORE_DATA: 'Cần thêm bằng chứng', NEEDS_REVIEW: 'Cần xem xét', IMPROVEMENT: 'Cải thiện so với baseline',
  NO_IMPROVEMENT: 'Không cải thiện so với baseline', INCONCLUSIVE: 'Chưa đủ cơ sở kết luận',
};

const VERDICT_LABELS_EN: Record<string, string> = {
  PASS: 'Passed', PASSED: 'Passed', FAILED: 'Failed', NOT_RUN: 'Not run', REVISE: 'Needs revision',
  NEED_MORE_DATA: 'Needs more evidence', NEEDS_REVIEW: 'Needs review', IMPROVEMENT: 'Improvement over baseline',
  NO_IMPROVEMENT: 'No improvement over baseline', INCONCLUSIVE: 'Inconclusive',
};

export function outputLabel(key: string, value: number | string | boolean, lang: 'en' | 'vi' = 'vi') {
  const dict = lang === 'en' ? OUTPUT_LABELS_EN : OUTPUT_LABELS_VI;
  const vdict = lang === 'en' ? VERDICT_LABELS_EN : VERDICT_LABELS_VI;
  const label = dict[key] || key;
  const formattedVal = typeof value === 'boolean'
    ? (value ? (lang === 'en' ? 'Yes' : 'Có') : (lang === 'en' ? 'No' : 'Không'))
    : vdict[String(value)] || value;
  return `${label}: ${formattedVal}`;
}
