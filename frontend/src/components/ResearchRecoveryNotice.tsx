import Link from 'next/link';
import type { ResearchTaskResponse } from '@/types';

export function researchBudgetBlocked(task: Pick<ResearchTaskResponse, 'current_step' | 'retry_blocked_reason'>) {
  return task.current_step === 'BUDGET_LIMIT' || task.retry_blocked_reason === 'TASK_BUDGET_LIMIT';
}

export function ResearchRecoveryNotice({task, isEn, busy, onContinue}: {
  task: ResearchTaskResponse; isEn: boolean; busy: boolean; onContinue: () => void;
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
  return <section aria-label={isEn ? 'Continue research' : 'Tiếp tục nghiên cứu'} className="mb-4 rounded-xl border border-zinc-200 bg-white p-4 text-sm">
    <p className="mb-3 text-zinc-700">{blocked
      ? (isEn ? 'This article cannot continue within its remaining allowance. Saved sources and results are kept.' : 'Giới hạn còn lại không đủ để tiếp tục bài này. Nguồn và kết quả đã lưu vẫn được giữ.')
      : (isEn ? 'Continue from the failed step using the remaining allowance.' : 'Tiếp tục từ bước lỗi, sử dụng phần giới hạn còn lại của bài.')}</p>
    {blocked ? <Link href="/" className="inline-block rounded-lg bg-zinc-900 px-4 py-2 font-medium text-white">
      {isEn ? 'Create new research' : 'Tạo nghiên cứu mới'}</Link>
      : <button type="button" disabled={busy} onClick={onContinue} className="rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-50">
        {busy ? (isEn ? 'Resuming…' : 'Đang tiếp tục…') : (isEn ? 'Continue from failed step' : 'Tiếp tục từ bước lỗi')}</button>}
  </section>;
}
