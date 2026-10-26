'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import { Activity, ArrowUpRight, Clock, FileText, Plus, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { currentStage } from '@/lib/monitoring';
import { useMonitorPoll } from '@/lib/use-monitor-poll';
import { PollStatus, StatusPill, formatTime } from '@/components/monitoring/MonitorUI';

export default function MonitorOverview() {
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState('');
  const load = useCallback((signal: AbortSignal) => api.tasks.list(page * 20, 21, signal), [page]);
  const { data, error, loading, lastSuccess, refresh } = useMonitorPoll(load);
  const tasks = data?.slice(0, 20) || [];
  const visible = tasks.filter(task => task.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const running = tasks.filter(task => task.status === 'RUNNING' || task.status === 'QUEUED').length;
  const waiting = tasks.filter(task => task.status.startsWith('WAITING')).length;
  const attention = tasks.filter(task => ['FAILED', 'NEEDS_REVIEW', 'PARTIAL'].includes(task.status)).length;

  return <main className="h-full overflow-y-auto bg-zinc-50 px-4 py-8 sm:px-8">
    <div className="mx-auto max-w-6xl space-y-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-blue-600">Research activity</p>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">Theo dõi các bài nghiên cứu</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">Biết bài nào đang được thực hiện, bài nào cần bạn phản hồi. Mở một bài để xem các bước và kết quả đã ghi nhận.</p>
        </div>
        <Link href="/" className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white hover:bg-zinc-700"><Plus size={16} /> Bài nghiên cứu mới</Link>
      </header>
      <div className="grid gap-4 sm:grid-cols-3">
        {[{ title: 'Đang chạy / xếp hàng', count: running, icon: Activity, tone: 'text-blue-600 bg-blue-50' },
          { title: 'Đang chờ bạn', count: waiting, icon: Clock, tone: 'text-amber-600 bg-amber-50' },
          { title: 'Cần kiểm tra', count: attention, icon: FileText, tone: 'text-violet-600 bg-violet-50' }].map(item => <div key={item.title} className="flex items-center gap-4 rounded-2xl border border-zinc-200 bg-white p-5">
            <span className={`rounded-xl p-3 ${item.tone}`}><item.icon size={22} /></span>
            <div><div className="text-2xl font-semibold">{data ? item.count : '—'}</div><div className="text-sm text-zinc-500">{item.title}</div></div>
          </div>)}
      </div>
      <p className="text-xs text-zinc-500">Số lượng tính trong tối đa 20 bài của trang hiện tại. Bài đang chờ không giữ worker; bạn có thể mở hoặc tạo bài khác.</p>
      <PollStatus error={error} lastSuccess={lastSuccess} refresh={refresh} />
      <section className="overflow-hidden rounded-2xl border border-zinc-200 bg-white" aria-label="Danh sách bài nghiên cứu">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 px-5 py-4">
          <h2 className="font-semibold">Bài của bạn · Trang {page + 1}</h2>
          <label className="flex items-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm text-zinc-500"><Search size={15} />
            <input aria-label="Lọc tiêu đề trong trang" placeholder="Lọc tiêu đề trong trang…" value={query} onChange={e => setQuery(e.target.value)} className="w-48 bg-transparent text-zinc-900 outline-none" />
          </label>
        </div>
        {loading && !data && <p role="status" className="p-8 text-sm text-zinc-500">Đang tải trạng thái…</p>}
        {!loading && data && visible.length === 0 && <p className="p-8 text-sm text-zinc-500">{tasks.length ? 'Không có tiêu đề khớp trong trang này.' : 'Chưa có bài nghiên cứu trên trang này.'}</p>}
        <ul className="divide-y divide-zinc-100">{visible.map(task => <li key={task.id}>
          <Link href={`/research/${task.id}/monitor`} className="group flex flex-wrap items-center justify-between gap-4 px-5 py-5 hover:bg-zinc-50">
            <div className="min-w-0 flex-1"><h3 className="break-words font-medium text-zinc-900">{task.title}</h3>
              <p className="mt-1 text-sm text-zinc-500">{currentStage(task.current_step)?.name || 'Chưa ghi nhận bước xử lý'} <span className="mx-1">·</span> Vòng nghiên cứu {task.current_iteration}</p>
              <p className="mt-2 text-xs text-zinc-400">Trạng thái cập nhật: {formatTime(task.updated_at)}</p>
            </div>
            <StatusPill status={task.status} /><ArrowUpRight size={18} className="text-zinc-400 group-hover:text-blue-600" />
          </Link>
        </li>)}</ul>
        <div className="flex justify-between gap-3 border-t border-zinc-100 p-4 text-sm">
          <button disabled={!page || loading} onClick={() => setPage(value => value - 1)} className="rounded-lg border border-zinc-200 px-3 py-2 disabled:opacity-40">Trang trước</button>
          <button disabled={!data || data.length <= 20 || loading} onClick={() => setPage(value => value + 1)} className="rounded-lg border border-zinc-200 px-3 py-2 disabled:opacity-40">Trang sau</button>
        </div>
      </section>
    </div>
  </main>;
}
