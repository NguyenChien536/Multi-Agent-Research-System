import Link from 'next/link';
import type { ResearchTaskResponse } from '@/types';

export function researchBudgetBlocked(task: Pick<ResearchTaskResponse, 'current_step' | 'retry_blocked_reason'>) {
  return task.current_step === 'BUDGET_LIMIT' || task.retry_blocked_reason === 'TASK_BUDGET_LIMIT';
}

export function ResearchRecoveryNotice({task, isEn, busy, onContinue, onExtend}: {
  task: ResearchTaskResponse; isEn: boolean; busy: boolean; onContinue: () => void; onExtend?: () => void;
}) {
  const blocked = researchBudgetBlocked(task);
  if (task.provider_wait && task.status === 'QUEUED') {
    const date = new Date(task.provider_wait.retry_at);
    return <div role="status" className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
      <strong>{isEn ? 'Waiting for the AI service' : 'Tạm chờ dịch vụ AI'}</strong>
      <p className="mt-1">{isEn ? 'Progress is saved. Automatic retry: ' : 'Tiến độ đã lưu. Tự tiếp tục lúc: '}
        {Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString(isEn ? 'en-GB' : 'vi-VN')}.</p>
    </div>;
  }
  if (!blocked && task.status !== 'FAILED') return null;
  const allowance = task.token_allowance;
  return <section id="research-recovery-controls" aria-label={isEn ? 'Continue research' : 'Tiếp tục nghiên cứu'} className="mb-4 rounded-xl border border-zinc-200 bg-white p-4 text-sm">
    <p className="mb-3 text-zinc-700">{blocked
      ? (isEn ? 'Research is paused at its allowance. Saved sources and writing are kept; review the limits below to continue.' : 'Bài tạm dừng do chạm hạn mức. Nguồn và phần đã viết vẫn được giữ; xem hạn mức bên dưới để tiếp tục.')
      : (isEn ? 'Continue from the failed step using the remaining allowance.' : 'Tiếp tục từ bước lỗi, sử dụng phần giới hạn còn lại của bài.')}</p>
    {allowance?.can_extend && onExtend && <div className="mb-3 rounded-lg bg-zinc-50 p-3">
      <p>{isEn ? 'New token limits: ' : 'Hạn mức token mới: '}
        {allowance.next_input_tokens.toLocaleString()} input / {allowance.next_output_tokens.toLocaleString()} output.</p>
      {allowance.next_max_llm_calls != null && allowance.next_timeout_seconds != null && <p className="mt-1">{isEn ? 'Total allowance: ' : 'Tổng hạn mức: '}{allowance.next_max_llm_calls} {isEn ? 'calls' : 'lượt gọi'} · {Math.round(allowance.next_timeout_seconds / 60)} {isEn ? 'active minutes' : 'phút xử lý'} · ${allowance.max_cost_usd?.toFixed(2)} {isEn ? 'estimated cost ceiling' : 'trần chi phí ước tính'}.</p>}
      <p className="mb-2 mt-1 text-xs text-zinc-500">{isEn ? 'Recorded usage is kept. The cost ceiling stays unchanged. Continuing can make additional API calls within that ceiling.' : 'Giữ lượng đã dùng và trần chi phí. Tiếp tục có thể gọi thêm API trong trần này.'}</p>
      <button type="button" disabled={busy} onClick={onExtend}
        className="rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-50">
        {busy ? (isEn ? 'Resuming…' : 'Đang tiếp tục…') : (isEn ? 'Approve limits and continue' : 'Duyệt hạn mức và tiếp tục')}
      </button>
    </div>}
    {blocked ? <Link href="/" className="inline-block rounded-lg border border-zinc-200 px-4 py-2 font-medium text-zinc-700">
      {isEn ? 'Create new research' : 'Tạo nghiên cứu mới'}</Link>
      : <button type="button" disabled={busy} onClick={onContinue} className="rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-50">
        {busy ? (isEn ? 'Resuming…' : 'Đang tiếp tục…') : (isEn ? 'Continue from failed step' : 'Tiếp tục từ bước lỗi')}</button>}
  </section>;
}
