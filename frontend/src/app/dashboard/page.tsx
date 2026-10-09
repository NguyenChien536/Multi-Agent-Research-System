'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, CheckCircle2, Clock, FileText, Plus, RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import type { ResearchTaskResponse } from '@/types';

const ACTIVE_STATUSES = new Set([
  'QUEUED', 'RUNNING', 'PLANNING', 'RESEARCHING', 'INDEXING',
  'ANALYZING', 'WRITING', 'REVIEWING', 'FINALIZING', 'RETRYING',
]);
const ATTENTION_STATUSES = new Set(['WAITING_APPROVAL', 'WAITING_USER_DATA', 'NEEDS_REVIEW', 'FAILED']);

function StatusBadge({ status }: { status: string }) {
  if (status === 'COMPLETED') {
    return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"><CheckCircle2 size={12} /> Hoàn thành</span>;
  }
  if (status === 'WAITING_APPROVAL' || status === 'WAITING_USER_DATA') {
    return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200"><Clock size={12} /> {status === 'WAITING_APPROVAL' ? 'Chờ duyệt' : 'Chờ dữ liệu'}</span>;
  }
  if (status === 'FAILED' || status === 'NEEDS_REVIEW') {
    return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200"><AlertCircle size={12} /> {status === 'FAILED' ? 'Thất bại' : 'Cần xem xét'}</span>;
  }
  if (ACTIVE_STATUSES.has(status)) {
    return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"><span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" /> {status === 'QUEUED' ? 'Đang chờ chạy' : 'Đang thực hiện'}</span>;
  }
  return <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-100 text-zinc-700">{status === 'PENDING' ? 'Chưa bắt đầu' : status === 'CANCELLED' ? 'Đã hủy' : status}</span>;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Không rõ' : new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

export default function DashboardPage() {
  const [tasks, setTasks] = useState<ResearchTaskResponse[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setTasks(await api.tasks.list(0, 100));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải danh sách bài nghiên cứu.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadTasks(); }, [loadTasks]);

  const filtered = useMemo(() => tasks.filter(task =>
    `${task.title} ${task.research_question}`.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi'))
  ), [tasks, query]);
  const activeCount = tasks.filter(task => ACTIVE_STATUSES.has(task.status)).length;
  const attentionCount = tasks.filter(task => ATTENTION_STATUSES.has(task.status)).length;

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-10">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Dashboard</h1>
            <p className="text-zinc-500 text-sm mt-1">Các bài nghiên cứu của bạn</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void loadTasks()} disabled={loading} aria-label="Tải lại danh sách"><RefreshCw size={16} /></Button>
            <Link href="/" className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-800"><Plus size={16} /> Nghiên cứu mới</Link>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-sm"><div className="text-zinc-500 text-sm font-medium mb-1">Bài đã tải</div><div className="text-3xl font-bold">{tasks.length}</div></div>
          <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-sm"><div className="text-zinc-500 text-sm font-medium mb-1">Đang thực hiện</div><div className="text-3xl font-bold">{activeCount}</div></div>
          <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-sm"><div className="text-zinc-500 text-sm font-medium mb-1">Cần chú ý</div><div className="text-3xl font-bold">{attentionCount}</div></div>
        </div>

        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-zinc-200 flex flex-col sm:flex-row justify-between items-center gap-4">
            <h2 className="font-semibold text-lg">Bài gần đây</h2>
            <div className="relative w-full sm:w-64">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input value={query} onChange={event => setQuery(event.target.value)} type="search" placeholder="Tìm kiếm..." aria-label="Tìm bài nghiên cứu" className="w-full pl-9 pr-4 py-2 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 transition-shadow" />
            </div>
          </div>
          {error && <div role="alert" className="p-5 text-sm text-red-700 bg-red-50">{error} <button className="underline ml-2" onClick={() => void loadTasks()}>Thử lại</button></div>}
          {loading ? <p className="p-8 text-center text-zinc-500">Đang tải bài nghiên cứu...</p> : !error && filtered.length === 0 ? <p className="p-8 text-center text-zinc-500">{query ? 'Không tìm thấy bài phù hợp.' : 'Chưa có bài nghiên cứu. Hãy tạo bài đầu tiên.'}</p> : !error && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead><tr className="bg-zinc-50/50 text-xs font-semibold text-zinc-500 uppercase tracking-wider border-b border-zinc-200"><th className="px-6 py-4">Tên bài nghiên cứu</th><th className="px-6 py-4">Độ sâu</th><th className="px-6 py-4">Trạng thái</th><th className="px-6 py-4">Cập nhật</th></tr></thead>
                <tbody className="divide-y divide-zinc-100">
                  {filtered.map(task => (
                    <tr key={task.id} className="hover:bg-zinc-50 transition-colors">
                      <td className="px-6 py-4"><Link href={`/research/${task.id}`} className="flex items-start gap-3"><span className="mt-0.5 w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0"><FileText size={16} className="text-zinc-600" /></span><span className="font-medium text-zinc-900 line-clamp-2 hover:underline">{task.title}</span></Link></td>
                      <td className="px-6 py-4 text-xs font-medium text-zinc-500">{task.research_depth}</td>
                      <td className="px-6 py-4"><StatusBadge status={task.status} /></td>
                      <td className="px-6 py-4 text-sm text-zinc-500 whitespace-nowrap">{formatDate(task.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
