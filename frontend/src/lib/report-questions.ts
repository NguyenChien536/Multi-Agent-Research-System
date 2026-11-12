export function safeSourceUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export const QUESTION_STATUS: Record<string, string> = {
  RUNNING: 'Đang tạo câu trả lời', ANSWERED: 'Đã trả lời',
  INSUFFICIENT_EVIDENCE: 'Chưa đủ bằng chứng', FAILED: 'Chưa thể trả lời', BUDGET_LIMIT: 'Đã chạm giới hạn',
};

export const QUESTION_STATUS_EN: Record<string, string> = {
  RUNNING: 'Generating answer', ANSWERED: 'Answered',
  INSUFFICIENT_EVIDENCE: 'Insufficient evidence', FAILED: 'Unable to answer', BUDGET_LIMIT: 'Resource limit reached',
};

export const QUESTION_ERRORS: Record<string, string> = {
  TIMEOUT: 'Đã hết thời gian chờ trả lời. Câu hỏi đã được lưu; bạn có thể thử lại bằng một câu hỏi mới.',
  INTERRUPTED: 'Lần trả lời bị gián đoạn. Câu hỏi đã được lưu nhưng chưa có câu trả lời hoàn chỉnh.',
  PROVIDER_ERROR: 'Dịch vụ AI chưa trả lời thành công. Bạn có thể thử lại sau.',
  INVALID_REFERENCE: 'Trích dẫn trả về chưa xác minh được với nguồn của phiên bản này, nên câu trả lời chưa được hiển thị.',
  TASK_CHANGED: 'Trạng thái bài đã thay đổi trong lúc trả lời. Kiểm tra lại bài trước khi hỏi tiếp.',
  BUDGET_LIMIT: 'Bài đã chạm giới hạn tài nguyên AI (ngân sách, số lần gọi hoặc token). Các câu trả lời đã lưu vẫn có thể xem lại.',
};

export const QUESTION_ERRORS_EN: Record<string, string> = {
  TIMEOUT: 'Response timed out. The question has been recorded; you may submit a new question.',
  INTERRUPTED: 'Answer generation was interrupted. The question was saved without a complete response.',
  PROVIDER_ERROR: 'AI provider error. Please try again later.',
  INVALID_REFERENCE: 'Returned citation could not be verified against sources in this version; answer withheld.',
  TASK_CHANGED: 'Research status changed while processing. Please review the workspace before asking again.',
  BUDGET_LIMIT: 'Research reached its AI resource budget ceiling (tokens, calls, or budget). Prior answers remain accessible.',
};

export function questionStatusLabel(status: string, lang: 'en' | 'vi' = 'vi'): string {
  return (lang === 'en' ? QUESTION_STATUS_EN[status] : QUESTION_STATUS[status]) || status;
}

export function questionErrorMessage(code: string, lang: 'en' | 'vi' = 'vi'): string {
  return (lang === 'en' ? QUESTION_ERRORS_EN[code] : QUESTION_ERRORS[code]) || (lang === 'en' ? 'An error occurred.' : 'Lần trả lời chưa hoàn tất.');
}
