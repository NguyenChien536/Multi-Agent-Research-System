'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { 
  AlertCircle, CheckCircle2, Clock, FileText, 
  LogOut, Play, Plus, RefreshCw, Search, Trash2, XCircle, ArrowUpRight 
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Components';
import { api } from '@/lib/api';
import type { ResearchTaskResponse } from '@/types';

const ACTIVE_STATUSES = new Set([
  'QUEUED', 'RUNNING', 'PLANNING', 'RESEARCHING', 'INDEXING',
  'ANALYZING', 'WRITING', 'REVIEWING', 'FINALIZING', 'RETRYING',
]);
const ATTENTION_STATUSES = new Set(['WAITING_APPROVAL', 'WAITING_USER_DATA', 'NEEDS_REVIEW', 'FAILED']);

function StatusBadge({ status }: { status: string }) {
  if (status === 'COMPLETED') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 size={12} /> Hoàn thành
      </span>
    );
  }
  if (status === 'WAITING_APPROVAL' || status === 'WAITING_USER_DATA') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
        <Clock size={12} /> {status === 'WAITING_APPROVAL' ? 'Chờ duyệt' : 'Chờ dữ liệu'}
      </span>
    );
  }
  if (status === 'FAILED' || status === 'NEEDS_REVIEW') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
        <AlertCircle size={12} /> {status === 'FAILED' ? 'Thất bại' : 'Cần xem xét'}
      </span>
    );
  }
  if (ACTIVE_STATUSES.has(status)) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
        {status === 'QUEUED' ? 'Đang chờ chạy' : 'Đang thực hiện'}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-100 text-zinc-700">
      {status === 'PENDING' ? 'Chưa bắt đầu' : status === 'CANCELLED' ? 'Đã hủy' : status}
    </span>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Không rõ' : new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

export default function DashboardPage() {
  const [tasks, setTasks] = useState<ResearchTaskResponse[]>([]);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'ATTENTION' | 'COMPLETED'>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

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

  const handleStartTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActionLoadingId(id);
    try {
      await api.tasks.start(id);
      await loadTasks();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể bắt đầu nghiên cứu.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCancelTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Bạn có chắc muốn hủy bài nghiên cứu này?')) return;
    setActionLoadingId(id);
    try {
      await api.tasks.cancel(id);
      await loadTasks();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể hủy bài nghiên cứu.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDeleteTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Bạn có chắc muốn xóa vĩnh viễn bài nghiên cứu này?')) return;
    setActionLoadingId(id);
    try {
      await api.tasks.delete(id);
      await loadTasks();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể xóa bài nghiên cứu.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleLogout = () => {
    api.auth.logout();
    window.location.assign('/login');
  };

  const filtered = useMemo(() => {
    return tasks.filter(task => {
      const matchQuery = `${task.title} ${task.research_question}`.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi'));
      if (!matchQuery) return false;
      if (statusFilter === 'ACTIVE') return ACTIVE_STATUSES.has(task.status);
      if (statusFilter === 'ATTENTION') return ATTENTION_STATUSES.has(task.status);
      if (statusFilter === 'COMPLETED') return task.status === 'COMPLETED';
      return true;
    });
  }, [tasks, query, statusFilter]);

  const activeCount = tasks.filter(task => ACTIVE_STATUSES.has(task.status)).length;
  const attentionCount = tasks.filter(task => ATTENTION_STATUSES.has(task.status)).length;
  const completedCount = tasks.filter(task => task.status === 'COMPLETED').length;

  return (
    <div className="flex flex-col min-h-screen bg-zinc-50">
      {/* Top Navbar */}
      <header className="w-full px-6 py-4 flex justify-between items-center z-20 border-b border-zinc-200 bg-white">
        <Link href="/" className="flex items-center gap-2.5 font-bold text-xl tracking-tight text-zinc-900">
          <div className="w-8 h-8 rounded-xl bg-zinc-900 text-white flex items-center justify-center text-sm shadow-md font-sans">S</div>
          <span>Synthia</span>
          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 border border-zinc-200">ATI</span>
        </Link>

        <div className="flex items-center gap-2">
          <Link 
            href="/" 
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-3.5 text-xs font-semibold text-white hover:bg-zinc-800 transition-colors shadow-sm"
          >
            <Plus size={14} /> Nghiên cứu mới
          </Link>
          <Button variant="ghost" className="h-9 text-xs" onClick={handleLogout} title="Đăng xuất khỏi hệ thống">
            <LogOut size={14} className="mr-1 text-zinc-500" /> Đăng xuất
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6 md:p-10">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Dashboard</h1>
            <p className="text-zinc-500 text-sm mt-1">Quản lý và theo dõi các bài nghiên cứu đa tác tử của bạn</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void loadTasks()} disabled={loading} aria-label="Tải lại danh sách">
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </Button>
            <Link 
              href="/" 
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-800 transition-colors shadow-sm"
            >
              <Plus size={16} /> Nghiên cứu mới
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div 
            onClick={() => setStatusFilter('ALL')}
            className={`p-5 rounded-2xl border transition-all cursor-pointer ${statusFilter === 'ALL' ? 'bg-zinc-900 text-white border-zinc-900 shadow-md' : 'bg-white text-zinc-900 border-zinc-200 hover:border-zinc-300'}`}
          >
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1 ${statusFilter === 'ALL' ? 'text-zinc-300' : 'text-zinc-500'}`}>Tất cả bài</div>
            <div className="text-3xl font-bold">{tasks.length}</div>
          </div>

          <div 
            onClick={() => setStatusFilter('ACTIVE')}
            className={`p-5 rounded-2xl border transition-all cursor-pointer ${statusFilter === 'ACTIVE' ? 'bg-blue-600 text-white border-blue-600 shadow-md' : 'bg-white text-zinc-900 border-zinc-200 hover:border-zinc-300'}`}
          >
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1 ${statusFilter === 'ACTIVE' ? 'text-blue-100' : 'text-blue-600'}`}>Đang thực hiện</div>
            <div className="text-3xl font-bold">{activeCount}</div>
          </div>

          <div 
            onClick={() => setStatusFilter('ATTENTION')}
            className={`p-5 rounded-2xl border transition-all cursor-pointer ${statusFilter === 'ATTENTION' ? 'bg-amber-600 text-white border-amber-600 shadow-md' : 'bg-white text-zinc-900 border-zinc-200 hover:border-zinc-300'}`}
          >
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1 ${statusFilter === 'ATTENTION' ? 'text-amber-100' : 'text-amber-600'}`}>Cần chú ý</div>
            <div className="text-3xl font-bold">{attentionCount}</div>
          </div>

          <div 
            onClick={() => setStatusFilter('COMPLETED')}
            className={`p-5 rounded-2xl border transition-all cursor-pointer ${statusFilter === 'COMPLETED' ? 'bg-emerald-600 text-white border-emerald-600 shadow-md' : 'bg-white text-zinc-900 border-zinc-200 hover:border-zinc-300'}`}
          >
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1 ${statusFilter === 'COMPLETED' ? 'text-emerald-100' : 'text-emerald-600'}`}>Hoàn thành</div>
            <div className="text-3xl font-bold">{completedCount}</div>
          </div>
        </div>

        {/* Task Table Card */}
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-zinc-200 flex flex-col sm:flex-row justify-between items-center gap-4 bg-zinc-50/50">
            <div className="flex items-center gap-3">
              <h2 className="font-semibold text-lg text-zinc-900">Danh sách bài nghiên cứu</h2>
              {statusFilter !== 'ALL' && (
                <button 
                  onClick={() => setStatusFilter('ALL')} 
                  className="text-xs text-blue-600 hover:underline font-medium"
                >
                  (Bỏ lọc trạng thái)
                </button>
              )}
            </div>
            
            <div className="relative w-full sm:w-72">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input 
                value={query} 
                onChange={event => setQuery(event.target.value)} 
                type="search" 
                placeholder="Tìm theo tiêu đề hoặc câu hỏi..." 
                aria-label="Tìm bài nghiên cứu" 
                className="w-full pl-9 pr-4 py-2 bg-white border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 transition-shadow" 
              />
            </div>
          </div>

          {error && (
            <div role="alert" className="p-5 text-sm text-red-700 bg-red-50 border-b border-red-200 flex items-center justify-between">
              <span>{error}</span>
              <button className="underline font-medium" onClick={() => void loadTasks()}>Thử lại</button>
            </div>
          )}

          {loading ? (
            <div className="p-12 text-center text-zinc-500">
              <RefreshCw size={24} className="mx-auto animate-spin mb-3 text-zinc-400" />
              <p>Đang tải danh sách bài nghiên cứu...</p>
            </div>
          ) : !error && filtered.length === 0 ? (
            <div className="p-12 text-center text-zinc-500 space-y-3">
              <FileText size={32} className="mx-auto text-zinc-300" />
              <p>{query ? 'Không tìm thấy bài nghiên cứu phù hợp.' : 'Chưa có bài nghiên cứu nào trong không gian này.'}</p>
              {!query && (
                <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-zinc-900 underline hover:text-zinc-700">
                  Tạo bài nghiên cứu đầu tiên <ArrowUpRight size={14} />
                </Link>
              )}
            </div>
          ) : !error && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wider border-b border-zinc-200">
                    <th className="px-6 py-4">Tên bài nghiên cứu</th>
                    <th className="px-6 py-4">Độ sâu</th>
                    <th className="px-6 py-4">Trạng thái</th>
                    <th className="px-6 py-4">Cập nhật</th>
                    <th className="px-6 py-4 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {filtered.map(task => {
                    const isTaskWorking = ACTIVE_STATUSES.has(task.status);
                    return (
                      <tr key={task.id} className="hover:bg-zinc-50/70 transition-colors">
                        <td className="px-6 py-4">
                          <Link href={`/research/${task.id}`} className="flex items-start gap-3 group">
                            <span className="mt-0.5 w-8 h-8 rounded-lg bg-zinc-100 group-hover:bg-zinc-200 flex items-center justify-center shrink-0 transition-colors">
                              <FileText size={16} className="text-zinc-600" />
                            </span>
                            <div>
                              <span className="font-semibold text-zinc-900 line-clamp-1 group-hover:text-blue-600 transition-colors">
                                {task.title}
                              </span>
                              <span className="text-xs text-zinc-500 line-clamp-1 mt-0.5">
                                {task.research_question}
                              </span>
                            </div>
                          </Link>
                        </td>

                        <td className="px-6 py-4">
                          <Badge variant="outline">{task.research_depth}</Badge>
                        </td>

                        <td className="px-6 py-4">
                          <StatusBadge status={task.status} />
                        </td>

                        <td className="px-6 py-4 text-xs text-zinc-500 whitespace-nowrap">
                          {formatDate(task.updated_at)}
                        </td>

                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {(task.status === 'PENDING' || task.status === 'CANCELLED') && (
                              <button
                                onClick={(e) => void handleStartTask(task.id, e)}
                                disabled={actionLoadingId === task.id}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors"
                                title={task.status === 'CANCELLED' ? "Chạy lại nghiên cứu" : "Bắt đầu nghiên cứu"}
                              >
                                <Play size={12} /> {task.status === 'CANCELLED' ? "Chạy lại" : "Bắt đầu"}
                              </button>
                            )}

                            {isTaskWorking && (
                              <button
                                onClick={(e) => void handleCancelTask(task.id, e)}
                                disabled={actionLoadingId === task.id}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-red-50 text-red-700 hover:bg-red-100 transition-colors"
                                title="Hủy nghiên cứu"
                              >
                                <XCircle size={12} /> Hủy
                              </button>
                            )}

                            {(task.status === 'COMPLETED' || task.status === 'CANCELLED' || task.status === 'FAILED') && (
                              <button
                                onClick={(e) => void handleDeleteTask(task.id, e)}
                                disabled={actionLoadingId === task.id}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                                title="Xóa bài nghiên cứu"
                              >
                                <Trash2 size={14} />
                              </button>
                            )}

                            <Link
                              href={`/research/${task.id}`}
                              className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 transition-colors"
                              title="Xem chi tiết"
                            >
                              <ArrowUpRight size={15} />
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  );
}
