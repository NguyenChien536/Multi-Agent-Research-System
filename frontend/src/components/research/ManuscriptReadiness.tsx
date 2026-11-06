import Link from 'next/link';
import type { ResearchReportResponse } from '@/types';

/** Report readiness belongs to its saved version, not the latest background job. */
export function ManuscriptReadiness({ report, taskId, isEn }: {
  report: ResearchReportResponse; taskId: string; isEn: boolean;
}) {
  const metadata = report.review_metadata;
  const notes: string[] = [];
  for (const key of ['manuscript_findings', 'bibliography_findings', 'lineage_findings', 'evidence_delivery_findings']) {
    const values = metadata?.[key];
    if (!Array.isArray(values)) continue;
    for (const value of values) {
      const message = typeof value === 'string' ? value
        : value && typeof value.message === 'string' ? value.message : '';
      if (message.trim()) notes.push(message.trim());
    }
  }
  for (const section of metadata?.section_reviews || []) notes.push(...(section.feedback || []));
  const findings = Array.from(new Set(notes));
  const incomplete = metadata?.provider_limited || metadata?.draft_recovery?.review_incomplete;
  const reason = metadata?.draft_recovery?.reason;
  const interruptedMessage = reason === 'MODEL_INVALID_JSON' || reason === 'MODEL_OUTPUT_TRUNCATED'
    ? (isEn ? 'The model could not complete a valid review response.' : 'Model chưa trả được kết quả phản biện đúng định dạng.')
    : (isEn ? 'The AI review was interrupted by a provider or allowance limit.' : 'Bước phản biện bị gián đoạn do dịch vụ AI hoặc giới hạn lượt chạy.');
  const passed = report.review_status === 'PASSED' && !findings.length && !metadata?.budget_limited && !incomplete;
  return <section aria-label={isEn ? 'Manuscript review' : 'Kiểm tra bản thảo'}
    className="print:hidden rounded-xl border border-zinc-200 bg-white p-4 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-sm font-semibold text-zinc-900">{passed
          ? (isEn ? 'Automated checks passed' : 'Đã qua kiểm tra tự động')
          : (isEn ? 'Draft ready to read · Review needed' : 'Đã có bản thảo · Cần kiểm tra')}</p>
        <p className="mt-1 text-xs text-zinc-600">{isEn
          ? 'Check the sources and claims before using this draft.'
          : 'Đối chiếu nguồn và luận điểm trước khi sử dụng.'}</p>
      </div>
      {report.version_number && <Link href={`/research/${taskId}/revisions?version=${report.version_number}`}
        className="rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white hover:bg-zinc-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
        {isEn ? 'Review & revise' : 'Kiểm tra và sửa bài'}
      </Link>}
    </div>
    {metadata?.budget_limited && <p className="text-xs text-amber-800">{isEn
      ? 'The run reached its budget limit. Some checks may be incomplete.'
      : 'Đã chạm giới hạn ngân sách. Một số bước kiểm tra có thể chưa hoàn tất.'}</p>}
    {incomplete && <div role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
      <p>{interruptedMessage} {isEn ? 'Your draft is saved; it has not passed review.' : 'Bản thảo đã lưu, chưa được xác nhận qua phản biện.'}</p>
      <Link href={`/research/${taskId}/monitor#execution-errors`} className="mt-1 inline-block underline">
        {isEn ? 'View review interruption' : 'Xem bước bị gián đoạn'}
      </Link>
    </div>}
    {findings.length > 0 && <details className="border-t border-zinc-100 pt-3">
      <summary className="cursor-pointer text-xs font-medium text-zinc-700">{isEn
        ? `View ${findings.length} review ${findings.length === 1 ? 'note' : 'notes'}` : `Xem ${findings.length} góp ý kiểm tra`}</summary>
      <ul className="mt-3 list-disc pl-5 space-y-2 text-xs leading-relaxed text-zinc-600">
        {findings.map(note => <li key={note}>{note}</li>)}
      </ul>
    </details>}
  </section>;
}
