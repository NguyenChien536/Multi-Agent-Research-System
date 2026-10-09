'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, Circle, Clock, FileText, RefreshCw } from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import { api } from '@/lib/api';
import type { ResearchReportResponse, ResearchTaskResponse } from '@/types';

const STAGES = [
  { title: 'Lập kế hoạch', statuses: ['PLANNING', 'WAITING_APPROVAL'] },
  { title: 'Thu thập và phân tích nguồn', statuses: ['RESEARCHING', 'INDEXING', 'ANALYZING'] },
  { title: 'Viết và phản biện', statuses: ['WRITING', 'REVIEWING', 'FINALIZING'] },
];
const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW', 'PARTIAL']);

function stageState(index: number, status: string): 'done' | 'active' | 'waiting' {
  if (status === 'COMPLETED') return 'done';
  const current = STAGES.findIndex(stage => stage.statuses.includes(status));
  if (current < 0) return 'waiting';
  return index < current ? 'done' : index === current ? 'active' : 'waiting';
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    PENDING: 'Chưa bắt đầu', QUEUED: 'Đang chờ chạy', PLANNING: 'Đang lập kế hoạch',
    WAITING_APPROVAL: 'Chờ duyệt kế hoạch', WAITING_USER_DATA: 'Chờ dữ liệu',
    RESEARCHING: 'Đang tìm nguồn', INDEXING: 'Đang lập chỉ mục', ANALYZING: 'Đang phân tích',
    WRITING: 'Đang viết', REVIEWING: 'Đang phản biện', FINALIZING: 'Đang hoàn thiện',
    RETRYING: 'Đang thử lại', COMPLETED: 'Hoàn thành', PARTIAL: 'Bản nháp chưa đầy đủ',
    NEEDS_REVIEW: 'Cần xem xét', FAILED: 'Thất bại', CANCELLED: 'Đã hủy',
  };
  return labels[status] ?? status;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Không rõ' : new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export default function WorkspacePage({ params }: { params: { id: string } }) {
  const [task, setTask] = useState<ResearchTaskResponse | null>(null);
  const [report, setReport] = useState<ResearchReportResponse | null>(null);
  const [error, setError] = useState('');
  const [reportError, setReportError] = useState('');
  const [activeTab, setActiveTab] = useState<'report' | 'details'>('report');
  const [reloadKey, setReloadKey] = useState(0);

  const loadReport = useCallback(async () => {
    setReportError('');
    try {
      const value = await api.tasks.getReport(params.id);
      if (value.research_task_id === params.id) setReport(value);
      else setReportError('Báo cáo không khớp bài nghiên cứu này.');
    } catch (err) {
      setReportError(err instanceof Error ? err.message : 'Không thể tải báo cáo.');
    }
  }, [params.id]);

  useEffect(() => {
    let active = true;
    setTask(null);
    setReport(null);
    setError('');
    setReportError('');

    const poll = async () => {
      try {
        const value = await api.tasks.get(params.id);
        if (!active) return;
        setTask(value);
        setError('');
        if (['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(value.status)) void loadReport();
        if (TERMINAL.has(value.status)) clearInterval(timer);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Không thể tải tiến trình nghiên cứu.');
        clearInterval(timer);
      }
    };

    const timer = setInterval(() => { void poll(); }, 5000);
    void poll();
    return () => { active = false; clearInterval(timer); };
  }, [params.id, loadReport, reloadKey]);

  if (error) {
    return <div className="p-8 text-center text-red-700" role="alert">{error}<div className="mt-4"><button className="underline" onClick={() => setReloadKey(value => value + 1)}>Thử lại</button></div></div>;
  }
  if (!task || task.id !== params.id) {
    return <div className="p-8 text-center text-zinc-500">Đang tải bài nghiên cứu...</div>;
  }

  const isWorking = !TERMINAL.has(task.status) && task.status !== 'WAITING_APPROVAL' && task.status !== 'WAITING_USER_DATA' && task.status !== 'PENDING';

  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-50">
      <div className="min-h-16 px-6 py-3 border-b border-zinc-200 bg-white flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div>
          <h1 className="font-semibold text-lg line-clamp-1">{task.title}</h1>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-zinc-500">
            <span className="flex items-center gap-1">{isWorking && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}{statusLabel(task.status)}</span>
            <span>•</span><span>Task ID: {task.id}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{task.research_depth}</Badge>
          <Badge>Vòng: {task.current_iteration}/{task.max_iterations}</Badge>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden flex-col lg:flex-row">
        <aside className="w-full lg:w-80 border-r border-zinc-200 bg-zinc-50/50 flex flex-col shrink-0 overflow-y-auto max-h-64 lg:max-h-none">
          <div className="p-4 border-b border-zinc-200"><h2 className="font-semibold text-sm uppercase tracking-wider text-zinc-500">Các giai đoạn</h2></div>
          <div className="p-4">
            <div className="relative border-l-2 border-zinc-200 ml-3 space-y-6">
              {STAGES.map((stage, index) => {
                const state = stageState(index, task.status);
                const Icon = state === 'done' ? CheckCircle2 : state === 'active' ? Clock : Circle;
                return <div key={stage.title} className="relative pl-6"><span className={`absolute -left-3.5 top-0.5 p-1 rounded-full border border-zinc-200 bg-white ${state === 'done' ? 'text-emerald-500' : state === 'active' ? 'text-blue-500' : 'text-zinc-300'}`}><Icon size={14} /></span><span className={`text-sm ${state === 'waiting' ? 'text-zinc-400' : 'font-medium text-zinc-900'}`}>{stage.title}</span></div>;
              })}
            </div>
          </div>
          <div className="p-4 border-t border-zinc-200 mt-auto bg-white text-xs text-zinc-600 space-y-2">
            <div className="flex justify-between"><span>Tokens đã dùng</span><strong>{task.total_tokens_used.toLocaleString('vi-VN')}</strong></div>
            <div className="flex justify-between"><span>Chi phí ước tính</span><strong>${Number(task.total_cost_usd).toFixed(4)}</strong></div>
            <div className="flex justify-between"><span>Cập nhật</span><span>{formatDate(task.updated_at)}</span></div>
          </div>
        </aside>

        <main className="flex-1 flex flex-col bg-white overflow-hidden">
          <div className="flex border-b border-zinc-200 px-2 bg-zinc-50 shrink-0">
            <button onClick={() => setActiveTab('report')} className={`px-4 py-3 text-sm font-medium border-b-2 ${activeTab === 'report' ? 'border-zinc-900 text-zinc-900' : 'border-transparent text-zinc-500'}`}>Bài báo</button>
            <button onClick={() => setActiveTab('details')} className={`px-4 py-3 text-sm font-medium border-b-2 ${activeTab === 'details' ? 'border-zinc-900 text-zinc-900' : 'border-transparent text-zinc-500'}`}>Thông tin nhiệm vụ</button>
            <button className="ml-auto px-4 text-zinc-500 hover:text-zinc-900" onClick={() => setReloadKey(value => value + 1)} aria-label="Làm mới"><RefreshCw size={16} /></button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 md:p-10">
            {activeTab === 'report' ? <div className="max-w-3xl mx-auto">
              {['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(task.status) ? report?.research_task_id === params.id ? <>{task.status !== 'COMPLETED' && <p className="mb-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{statusLabel(task.status)} — nội dung này chưa phải bài báo hoàn chỉnh.</p>}<div className="flex items-center gap-2 mb-6"><FileText size={20} /><h2 className="text-xl font-semibold">{report.title}</h2></div><pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-zinc-800">{report.content_markdown}</pre></> : <div className="text-zinc-600">{reportError || 'Đang tải bài báo...'}{reportError && <button className="underline ml-2" onClick={() => void loadReport()}>Thử lại</button>}</div>
                : <Card className="p-6 text-sm text-zinc-600">{task.status === 'FAILED' || task.status === 'CANCELLED' ? 'Bài nghiên cứu đã dừng và chưa có bài báo hoàn chỉnh.' : task.status === 'WAITING_APPROVAL' || task.status === 'WAITING_USER_DATA' ? 'Bài nghiên cứu đang chờ thao tác của bạn. Chưa có bài báo hoàn chỉnh.' : 'Bài báo sẽ xuất hiện khi workflow hoàn thành. Trạng thái hiện tại được lấy từ API.'}</Card>}
            </div> : <div className="max-w-3xl mx-auto"><Card className="p-6 space-y-4"><h2 className="text-lg font-semibold">Thông tin nhiệm vụ</h2><div><span className="font-medium text-sm">Câu hỏi nghiên cứu</span><p className="text-zinc-600 mt-1">{task.research_question}</p></div>{task.description && <div><span className="font-medium text-sm">Mô tả</span><p className="text-zinc-600 mt-1">{task.description}</p></div>}<div className="text-sm text-zinc-500">Tạo lúc {formatDate(task.created_at)}</div><Link className="inline-block text-sm underline" href="/dashboard">Quay lại danh sách bài</Link></Card></div>}
          </div>
        </main>
      </div>
    </div>
  );
}
