'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Activity, ArrowLeft, ArrowUpRight, AlertTriangle, CheckCircle2, Circle, Clock, FileText } from 'lucide-react';
import { api } from '@/lib/api';
import { currentStage, stagesFor, stageKey, activityStage, outputLabel } from '@/lib/monitoring';
import { useMonitorPoll } from '@/lib/use-monitor-poll';
import { PollStatus, StatusPill, formatTime } from '@/components/monitoring/MonitorUI';

const ACTIONS: Record<string, { title: string; text: string; button: string }> = {
  REVIEW_PLAN: { title: 'Kế hoạch đang chờ bạn duyệt', text: 'Xem hướng nghiên cứu và truy vấn. Bạn có thể duyệt hoặc gửi góp ý trong workspace.', button: 'Xem kế hoạch' },
  UPLOAD_DATA: { title: 'Đang chờ dữ liệu nghiên cứu', text: 'Thực hiện theo protocol, tải tệp kết quả và khai báo nguồn dữ liệu để tiếp tục. Trong lúc chờ, bạn có thể làm bài khác.', button: 'Mở bài và thêm dữ liệu' },
  START_RESEARCH: { title: 'Bài chưa bắt đầu chạy', text: 'Kiểm tra câu hỏi, nguồn riêng và cấu hình trước khi bắt đầu.', button: 'Mở bài nghiên cứu' },
  CHECK_FAILURE: { title: 'Lần thực hiện này gặp lỗi', text: 'Xem bước gần nhất và nhật ký bên dưới. Đây là trạng thái đã ghi nhận; nguyên nhân chi tiết cần đối chiếu log vận hành.', button: 'Mở bài nghiên cứu' },
  CANCELLED: { title: 'Bài đã được hủy', text: 'Các kết quả đã lưu vẫn được giữ. Bạn có thể xem lại bài trước khi quyết định bước tiếp theo.', button: 'Xem bài nghiên cứu' },
  REVIEW_LIMIT: { title: 'Đã dừng do giới hạn tài nguyên', text: 'Hệ thống đã ghi nhận giới hạn ngân sách hoặc thời gian hoạt động. Kiểm tra các kết quả đã có trước khi sử dụng.', button: 'Kiểm tra bài nghiên cứu' },
  REVIEW_REPORT: { title: 'Bản thảo cần bạn kiểm tra', text: 'Đọc nội dung, trích dẫn và nhận xét phản biện trước khi sử dụng bản thảo.', button: 'Kiểm tra bản thảo' },
  REVIEW_RUN: { title: 'Cần kiểm tra lần thực hiện', text: 'Chưa ghi nhận bản thảo hoàn chỉnh. Hãy xem các bước và kết quả hiện có.', button: 'Mở bài nghiên cứu' },
  READ_REPORT: { title: 'Bản thảo đã được tạo', text: 'Bạn có thể mở bài để đọc, đối chiếu bằng chứng và tải các tệp kết quả.', button: 'Đọc bản thảo' },
  REPORT_UNAVAILABLE: { title: 'Chưa tìm thấy bản thảo đã lưu', text: 'Trạng thái hoàn thành và dữ liệu báo cáo chưa khớp. Cần kiểm tra trước khi sử dụng.', button: 'Mở bài nghiên cứu' },
  WAIT: { title: 'Hệ thống đang tiếp tục xử lý', text: 'Bạn có thể rời trang hoặc làm bài khác. Trạng thái và các kết quả đã ghi nhận sẽ được tải lại khi quay lại.', button: 'Mở workspace' },
};

export default function ResearchMonitorPage() {
  const { id } = useParams<{ id: string }>();
  const [historyPage, setHistoryPage] = useState({ taskId: id, offset: 0 });
  const offset = historyPage.taskId === id ? historyPage.offset : 0;
  const load = useCallback((signal: AbortSignal) => api.tasks.getMonitor(id, offset, 20, signal), [id, offset]);
  const { data, error, loading, lastSuccess, refresh } = useMonitorPoll(load, 4000);
  const snapshot = data?.task_id === id ? data : null;
  const action = snapshot ? ACTIONS[snapshot.next_action] || ACTIONS.WAIT : null;
  const current = currentStage(snapshot?.current_step);

  return <main className="h-full overflow-y-auto bg-zinc-50 px-4 py-7 sm:px-8">
    <div className="mx-auto max-w-6xl space-y-6">
      <Link href="/research/monitor" className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900"><ArrowLeft size={15} /> Tất cả bài nghiên cứu</Link>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Theo dõi thực hiện</p>
          <h1 className="mt-2 break-words text-2xl font-semibold tracking-tight sm:text-3xl">{snapshot?.title || 'Tiến độ bài nghiên cứu'}</h1>
          {snapshot?.workflow && <p className="mt-2 text-xs text-zinc-500">Lần nghiên cứu {snapshot.workflow.run_number} · Kế hoạch v{snapshot.workflow.plan_version} · Bắt đầu {formatTime(snapshot.workflow.started_at)}</p>}
        </div>{snapshot && <StatusPill status={snapshot.status} />}
      </header>
      <PollStatus error={error} lastSuccess={lastSuccess} refresh={refresh} />
      {loading && !snapshot && <p role="status" className="rounded-2xl border bg-white p-8 text-zinc-500">Đang tải tiến độ…</p>}
      {snapshot && action && <>
        {snapshot.worker_lease_expired && <div role="alert" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle size={20} className="shrink-0" /><p>Thời hạn nhận việc của worker đã hết. Hệ thống có thể cần phục hồi lần chạy; chưa đủ cơ sở kết luận agent vẫn đang hoạt động.</p></div>}
        <section className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
          <div className="grid gap-6 p-6 lg:grid-cols-2">
            <div><span className="inline-flex items-center gap-2 text-xs font-medium text-blue-600"><Activity size={15} /> {snapshot.status === 'RUNNING' ? 'Bước xử lý gần nhất' : 'Bước đã ghi nhận gần nhất'}</span>
              <h2 className="mt-3 text-2xl font-semibold">{current?.name || (snapshot.status === 'QUEUED' ? 'Chờ lượt thực hiện' : 'Chưa ghi nhận bước xử lý')}</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">{current?.description || 'Các bước thực tế sẽ xuất hiện khi workflow bắt đầu ghi nhận tiến độ.'}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-zinc-500"><span className="rounded-lg bg-zinc-100 px-3 py-2">Vòng nghiên cứu {snapshot.current_iteration}</span><span className="rounded-lg bg-zinc-100 px-3 py-2">Lượt worker {snapshot.attempt_number}</span></div>
            </div>
            <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-5"><h2 className="font-semibold text-zinc-900">{action.title}</h2><p className="mt-2 text-sm leading-6 text-zinc-600">{action.text}</p>
              <Link href={`/research/${id}`} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-700">{action.button}<ArrowUpRight size={15} /></Link>
            </div>
          </div>
          <div className="border-t border-zinc-100 bg-zinc-50/50 px-6 py-4"><div className="flex flex-wrap gap-2">{stagesFor(snapshot.research_type).map(stage => <span key={stage.key} className={`rounded-lg border px-3 py-2 text-xs ${stage.key === stageKey(snapshot.current_step) ? 'border-blue-200 bg-blue-50 font-medium text-blue-800' : 'border-zinc-200 bg-white text-zinc-400'}`}>{stage.name}</span>)}</div>
            <p className="mt-3 text-xs leading-5 text-zinc-500">Workflow có thể quay lại tìm nguồn hoặc sửa bản thảo. Chặng tô sáng là bước gần nhất, không phải phần trăm hoàn thành. Các khối xử lý tài liệu, runner và kiểm trích dẫn là module hỗ trợ agent.</p>
          </div>
        </section>
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Kết quả đã lưu">
          {[['Nguồn thu thập', snapshot.counts.sources], ['Luận điểm có bằng chứng', snapshot.counts.verified_claims], ['Phiên bản bài báo', snapshot.counts.report_versions], ['Tệp kết quả', snapshot.counts.artifacts]].map(([label, count]) => <div key={label} className="rounded-xl border border-zinc-200 bg-white p-5"><p className="text-xs text-zinc-500">{label}</p><p className="mt-2 text-2xl font-semibold">{count}</p></div>)}
        </section>
        {(snapshot.counts.pending_sources > 0 || snapshot.counts.failed_sources > 0) && <p className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-900">Tài liệu: {snapshot.counts.pending_sources} đang xử lý, {snapshot.counts.failed_sources} xử lý lỗi. Nguồn chưa sẵn sàng chưa được coi là bằng chứng.</p>}
        <div className="grid items-start gap-6 lg:grid-cols-3">
          <section className="rounded-2xl border border-zinc-200 bg-white lg:col-span-2" aria-label="Nhật ký hoạt động">
            <div className="border-b border-zinc-100 p-5"><h2 className="flex items-center gap-2 font-semibold"><Clock size={18} className="text-blue-600" /> Nhật ký hoạt động</h2><p className="mt-2 text-xs leading-5 text-zinc-500">Mới nhất trước · Gồm các lần thực hiện đã lưu của bài này. Chi tiết thường xuất hiện khi một bước kết thúc; đây là tóm tắt thao tác và kết quả, không phải suy nghĩ nội bộ của AI.</p></div>
            {!snapshot.activities.length && <div className="p-7 text-sm leading-6 text-zinc-500">Chưa có hoạt động được lưu ở trang này. Bước hiện tại được hiển thị phía trên ngay cả khi agent chưa kết thúc.</div>}
            <ol className="divide-y divide-zinc-100">{snapshot.activities.map(activity => <li key={activity.id} className="flex gap-3 p-5">
              <span className={`mt-1 rounded-full p-2 ${activity.status === 'FAILED' ? 'bg-red-50 text-red-600' : activity.status === 'SUCCESS' ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'}`}>{activity.status === 'SUCCESS' ? <CheckCircle2 size={16} /> : <Circle size={16} />}</span>
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-semibold">{activityStage(activity.agent)?.name || 'Hoạt động hệ thống'}</h3><StatusPill status={activity.status} /></div>
                <p className="mt-1 text-xs text-zinc-400">{activityStage(activity.agent)?.agent || 'System'} · {formatTime(activity.started_at)} · {Math.max(0, activity.duration_ms / 1000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} giây · Vòng {activity.iteration}</p>
                <div className="mt-3 flex flex-wrap gap-2">{Object.entries(activity.output).map(([key, value]) => <span key={key} className="rounded-lg bg-zinc-50 px-2.5 py-1.5 text-xs text-zinc-600">{outputLabel(key, value)}</span>)}</div>
                {activity.has_error && <p className="mt-2 text-xs text-red-700">Bước này có ghi nhận lỗi. Chi tiết kỹ thuật được lưu trong log vận hành.</p>}
              </div>
            </li>)}</ol>
            <div className="flex items-center justify-between gap-2 border-t border-zinc-100 p-4 text-xs text-zinc-500"><button disabled={!offset} onClick={() => setHistoryPage({ taskId: id, offset: Math.max(0, offset - 20) })} className="rounded-lg border px-3 py-2 disabled:opacity-40">Mới hơn</button><span>{snapshot.activities.length ? `${offset + 1}–${offset + snapshot.activities.length} / ${snapshot.activity_total}` : '0 hoạt động ở trang này'}</span><button disabled={offset + 20 >= snapshot.activity_total} onClick={() => setHistoryPage({ taskId: id, offset: offset + 20 })} className="rounded-lg border px-3 py-2 disabled:opacity-40">Cũ hơn</button></div>
          </section>
          <aside className="space-y-4">
            <section className="rounded-2xl border border-zinc-200 bg-white p-5"><h2 className="font-semibold">Tài nguyên đã ghi nhận</h2><p className="mt-4 text-3xl font-semibold">${snapshot.estimated_cost_usd.toFixed(4)}</p><p className="mt-1 text-xs text-zinc-500">Chi phí ước tính · {snapshot.accounting_source === 'PROVIDER_LEDGER' ? 'sổ theo dõi provider' : 'lịch sử agent'}</p><dl className="mt-5 space-y-3 text-sm"><div className="flex justify-between"><dt className="text-zinc-500">Đặt chỗ chưa đối chiếu</dt><dd>${snapshot.reserved_cost_usd.toFixed(4)}</dd></div><div className="flex justify-between"><dt className="text-zinc-500">Token đã ghi nhận</dt><dd>{snapshot.recorded_tokens.toLocaleString('vi-VN')}</dd></div><div className="flex justify-between"><dt className="text-zinc-500">Lần phân tích</dt><dd>{snapshot.counts.experiments}</dd></div></dl><p className="mt-4 text-xs leading-5 text-zinc-400">Chi phí có thể cập nhật sau khi request hoàn tất; không phải hóa đơn chính thức.</p></section>
            <section className="rounded-2xl border border-zinc-200 bg-white p-5"><h2 className="flex items-center gap-2 font-semibold"><FileText size={16} /> Mốc thời gian</h2><dl className="mt-4 space-y-3 text-xs"><div><dt className="text-zinc-400">Tạo bài</dt><dd className="mt-1">{formatTime(snapshot.created_at)}</dd></div><div><dt className="text-zinc-400">Trạng thái cập nhật</dt><dd className="mt-1">{formatTime(snapshot.updated_at)}</dd></div><div><dt className="text-zinc-400">Kết thúc ghi nhận</dt><dd className="mt-1">{formatTime(snapshot.completed_at)}</dd></div></dl></section>
          </aside>
        </div>
      </>}
    </div>
  </main>;
}
