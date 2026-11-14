import Link from 'next/link';
import type { ResearchTaskResponse } from '@/types';

const LIMIT_LABELS: Record<string, { en: string; vi: string }> = {
  input_tokens: { en: 'input tokens', vi: 'token đầu vào' },
  output_tokens: { en: 'output tokens', vi: 'token đầu ra' },
  llm_calls: { en: 'model calls', vi: 'lượt gọi model' },
  active_time: { en: 'processing time', vi: 'thời gian xử lý' },
  cost: { en: 'estimated cost', vi: 'chi phí ước tính' },
};

function blockedLimitText(limits: string[] | undefined, isEn: boolean): string {
  return (limits ?? []).map(limit => LIMIT_LABELS[limit]?.[isEn ? 'en' : 'vi'] ?? limit).join(', ');
}

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
      <strong>{task.provider_wait.reason === 'PROVIDER_DAILY_LIMIT' ? (isEn ? 'Waiting for the daily allowance' : 'Đang chờ cấp lại hạn mức ngày') : (isEn ? 'Waiting for the AI service' : 'Tạm chờ dịch vụ AI')}</strong>
      <p className="mt-1">{isEn ? 'Progress is saved. Automatic retry: ' : 'Tiến độ đã lưu. Tự tiếp tục lúc: '}
        {Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(isEn ? 'en-GB' : 'vi-VN')}.</p>
      <p className="mt-2 text-xs">{isEn ? 'You can close this page. Research will resume automatically in the background. Waiting does not consume active processing time. You can stop the article from its header.' : 'Bạn có thể đóng trang. Hệ thống sẽ tự động tiếp tục xử lý ở chế độ nền. Thời gian chờ không trừ hạn mức xử lý. Bạn vẫn có thể dừng bài bằng nút ở đầu trang.'}</p>
    </div>;
  }
  if (!blocked && task.status !== 'FAILED') return null;
  const allowance = task.token_allowance;
  return <section id="research-recovery-controls" aria-label={isEn ? 'Continue research' : 'Tiếp tục nghiên cứu'} className="mb-4 rounded-xl border border-zinc-200 bg-white p-4 text-sm shadow-xs">
    <p className="mb-3 text-zinc-700 font-medium">{blocked
      ? (isEn ? 'Research is paused at its allowance. Saved sources and writing are kept; review the limits below to continue.' : 'Bài tạm dừng do chạm hạn mức. Nguồn và phần đã viết vẫn được giữ; xem hạn mức bên dưới để tiếp tục.')
      : (isEn ? 'Continue from the failed step using the remaining allowance.' : 'Tiếp tục từ bước lỗi, sử dụng phần giới hạn còn lại của bài.')}</p>

    {/* Recorded usage metrics grid */}
    {allowance && (
      <div className="mb-3 grid grid-cols-2 sm:grid-cols-4 gap-2 rounded-lg border border-zinc-200 bg-zinc-50/70 p-3 text-xs">
        <div>
          <span className="text-zinc-500 font-medium block">{isEn ? 'Cost Used' : 'Chi phí đã dùng'}</span>
          <span className="font-mono font-bold text-zinc-900">
            {allowance.cost_used_usd != null ? `$${allowance.cost_used_usd.toFixed(4)}` : '—'}
            <span className="text-zinc-500 font-normal"> / {allowance.max_cost_usd != null ? `$${allowance.max_cost_usd.toFixed(2)}` : '—'}</span>
          </span>
        </div>
        <div>
          <span className="text-zinc-500 font-medium block">{isEn ? 'Model Calls' : 'Lượt gọi model'}</span>
          <span className="font-mono font-bold text-zinc-900">
            {allowance.calls_used ?? '—'}
            <span className="text-zinc-500 font-normal"> / {allowance.max_llm_calls ?? '—'}</span>
          </span>
        </div>
        <div>
          <span className="text-zinc-500 font-medium block">{isEn ? 'Input Tokens' : 'Token đầu vào'}</span>
          <span className="font-mono font-bold text-zinc-900">
            {allowance.input_used ? allowance.input_used.toLocaleString() : '0'}
            <span className="text-zinc-500 font-normal"> / {allowance.max_input_tokens != null ? allowance.max_input_tokens.toLocaleString() : '—'}</span>
          </span>
        </div>
        <div>
          <span className="text-zinc-500 font-medium block">{isEn ? 'Output Tokens' : 'Token tạo ra'}</span>
          <span className="font-mono font-bold text-zinc-900">
            {allowance.output_used ? allowance.output_used.toLocaleString() : '0'}
            <span className="text-zinc-500 font-normal"> / {allowance.max_output_tokens != null ? allowance.max_output_tokens.toLocaleString() : '—'}</span>
          </span>
        </div>
      </div>
    )}

    {/* Extension proposal box */}
    {allowance?.can_extend && onExtend && <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50/60 p-3.5">
      <p className="font-semibold text-emerald-950">{isEn ? 'New token limits: ' : 'Hạn mức token mới: '}
        {allowance.next_input_tokens.toLocaleString()} input / {allowance.next_output_tokens.toLocaleString()} output.</p>
      {allowance.next_max_cost_usd != null && allowance.next_max_cost_usd > (allowance.max_cost_usd ?? 0) ? (
        <p className="mt-1 text-emerald-900">
          {isEn ? 'Total allowance: ' : 'Tổng hạn mức: '}
          {allowance.next_max_llm_calls} {isEn ? 'calls' : 'lượt gọi'} · {Math.round((allowance.next_timeout_seconds ?? 1800) / 60)} {isEn ? 'active minutes' : 'phút xử lý'} · ${(allowance.next_max_cost_usd).toFixed(2)} {isEn ? 'estimated cost ceiling' : 'trần chi phí ước tính'}.
        </p>
      ) : (
        allowance.next_max_llm_calls != null && allowance.next_timeout_seconds != null && <p className="mt-1 text-emerald-900">{isEn ? 'Total allowance: ' : 'Tổng hạn mức: '}{allowance.next_max_llm_calls} {isEn ? 'calls' : 'lượt gọi'} · {Math.round(allowance.next_timeout_seconds / 60)} {isEn ? 'active minutes' : 'phút xử lý'} · ${allowance.max_cost_usd?.toFixed(2)} {isEn ? 'estimated cost ceiling' : 'trần chi phí ước tính'}.</p>
      )}
      {allowance.next_max_cost_usd != null && allowance.next_max_cost_usd > (allowance.max_cost_usd ?? 0) ? (
        <p className="mb-2.5 mt-1 text-xs text-emerald-800">
          {isEn
            ? `Recorded usage is kept. Cost ceiling will be raised to $${allowance.next_max_cost_usd.toFixed(2)}. Continuing will make additional calls within that ceiling.`
            : `Giữ lượng đã dùng. Trần chi phí sẽ được tăng lên $${allowance.next_max_cost_usd.toFixed(2)}. Tiếp tục sẽ thực hiện thêm lượt gọi trong trần mới.`}
        </p>
      ) : (
        <p className="mb-2.5 mt-1 text-xs text-zinc-600">{isEn ? 'Recorded usage is kept. The cost ceiling stays unchanged. Continuing can make additional API calls within that ceiling.' : 'Giữ lượng đã dùng và trần chi phí. Tiếp tục có thể gọi thêm API trong trần này.'}</p>
      )}
      <button type="button" disabled={busy} onClick={onExtend}
        className="rounded-lg bg-emerald-700 hover:bg-emerald-800 px-4 py-2 font-medium text-white disabled:opacity-50 transition-colors shadow-xs cursor-pointer">
        {busy ? (isEn ? 'Resuming…' : 'Đang tiếp tục…') : (isEn ? 'Approve limits and continue' : 'Duyệt hạn mức và tiếp tục')}
      </button>
    </div>}

    {/* Explain the limiting resource without showing internal reason codes. */}
    {blocked && !allowance?.can_extend && (
      <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
        <p className="font-semibold">
          {isEn ? 'This article cannot continue within its current limits' : 'Bài này không thể tiếp tục trong hạn mức hiện tại'}
        </p>
        <p className="mt-1">
          {isEn
            ? `Saved work is preserved. ${allowance?.blocked_limits?.length ? `The system ceiling has been reached for: ${blockedLimitText(allowance.blocked_limits, true)}. ` : ''}Check the limits above before starting a new research task.`
            : `Phần đã lưu vẫn còn. ${allowance?.blocked_limits?.length ? `Đã đạt trần hệ thống cho: ${blockedLimitText(allowance.blocked_limits, false)}. ` : ''}Kiểm tra hạn mức ở trên trước khi tạo bài mới.`}
        </p>
      </div>
    )}

    {blocked ? <Link href="/" className="inline-block rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 px-4 py-2 font-medium text-zinc-700 transition-colors">
      {isEn ? 'Create new research' : 'Tạo nghiên cứu mới'}</Link>
      : <button type="button" disabled={busy} onClick={onContinue} className="rounded-lg bg-emerald-700 hover:bg-emerald-800 px-4 py-2 font-medium text-white disabled:opacity-50 transition-colors shadow-xs cursor-pointer">
        {busy ? (isEn ? 'Resuming…' : 'Đang tiếp tục…') : (isEn ? 'Continue from failed step' : 'Tiếp tục từ bước lỗi')}</button>}
  </section>;
}
