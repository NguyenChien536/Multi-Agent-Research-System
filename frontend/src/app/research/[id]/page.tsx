'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import { api } from '@/lib/api';
import { ResearchTaskResponse, ResearchReportResponse } from '@/types';
import { Card, Badge } from '@/components/ui/Components';

export default function ResearchDashboard({ params }: { params: { id: string } }) {
  const [task, setTask] = useState<ResearchTaskResponse | null>(null);
  const [error, setError] = useState('');
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const currentTaskIdRef = useRef(params.id);

  const [report, setReport] = useState<ResearchReportResponse | null>(null);
  const [reportError, setReportError] = useState('');
  const [isLoadingReport, setIsLoadingReport] = useState(false);

  const fetchReport = useCallback(async (taskId: string) => {
    try {
      setIsLoadingReport(true);
      setReportError('');
      const data = await api.tasks.getReport(taskId);
      if (currentTaskIdRef.current === taskId) setReport(data);
    } catch (err: any) {
      if (currentTaskIdRef.current === taskId) {
        setReportError('Không thể tải nội dung báo cáo.');
      }
    } finally {
      if (currentTaskIdRef.current === taskId) setIsLoadingReport(false);
    }
  }, []);

  const fetchTask = useCallback(async () => {
    try {
      const data = await api.tasks.get(params.id);
      if (currentTaskIdRef.current !== params.id) return;
      setTask(data);

      if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(data.status)) {
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      }

      if (data.status === 'COMPLETED') {
        await fetchReport(data.id);
      }
    } catch (err: any) {
      if (currentTaskIdRef.current !== params.id) return;
      setError('Không thể tải thông tin tiến trình nghiên cứu.');
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    }
  }, [fetchReport, params.id]);

  useEffect(() => {
    currentTaskIdRef.current = params.id;
    setTask(null);
    setError('');
    setReport(null);
    setReportError('');
    setIsLoadingReport(false);

    void fetchTask();
    pollIntervalRef.current = setInterval(fetchTask, 5000);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [fetchTask, params.id]);

  const isCompleted = task?.status === 'COMPLETED';

  if (error) {
    return <div className="p-8 text-center text-red-500">{error}</div>;
  }

  if (!task || task.id !== params.id) {
    return <div className="p-8 text-center text-zinc-500 animate-pulse">Đang tải dữ liệu kết nối...</div>;
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 p-4 md:p-8">
      <div className="max-w-6xl mx-auto flex flex-col gap-6">

        {/* Header */}
        <header className="flex flex-col gap-2 pb-6 border-b border-zinc-200">
          <div className="flex items-center gap-3">
            <Badge variant="outline">{task.status}</Badge>
            <span className="text-zinc-400 text-sm">ID: {task.id.split('-')[0]}...</span>
          </div>
          <h1 className="text-2xl font-semibold">{task.title}</h1>
          <p className="text-zinc-500">{task.research_question}</p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Progress Sidebar */}
          <div className="col-span-1 flex flex-col gap-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Tiến trình (Polling)</h2>
            <Card className="p-5 flex flex-col gap-4">
              <StepItem
                title="Khởi tạo Task & Lập kế hoạch"
                status={['PENDING', 'QUEUED', 'PLANNING'].includes(task.status) ? 'active' : 'done'}
              />
              <StepItem
                title="Thu thập & Phân tích Nguồn"
                status={['RESEARCHING', 'INDEXING', 'ANALYZING'].includes(task.status) ? 'active' : (isCompleted ? 'done' : 'waiting')}
              />
              <StepItem
                title="Biên soạn & Phản biện Báo cáo"
                status={['WRITING', 'REVIEWING', 'FINALIZING'].includes(task.status) ? 'active' : (isCompleted ? 'done' : 'waiting')}
              />
            </Card>

            <Card className="p-5 flex flex-col gap-2 bg-zinc-900 text-zinc-50 border-none">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Chi phí tiêu thụ</h3>
              <div className="flex justify-between items-center">
                <span className="text-sm">Tokens:</span>
                <span className="font-medium">{task.total_tokens_used.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Chi phí ước tính:</span>
                <span className="font-medium">${task.total_cost_usd.toFixed(4)}</span>
              </div>
            </Card>
          </div>

          {/* Report Area */}
          <div className="col-span-1 lg:col-span-2 flex flex-col gap-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Kết quả Báo cáo</h2>

            <Card className="p-8 min-h-[500px] flex flex-col">
              {task.status === 'FAILED' || task.status === 'CANCELLED' ? (
                <div className="flex-1 flex items-center justify-center text-zinc-500">
                  Nghiên cứu kết thúc với trạng thái {task.status}.
                </div>
              ) : !isCompleted ? (
                <div className="flex-1 flex flex-col items-center justify-center text-zinc-400 gap-4">
                  <div className="w-8 h-8 rounded-full border-2 border-zinc-200 border-t-zinc-900 animate-spin" />
                  <p className="text-sm">AI đang tổng hợp và phân tích dữ liệu...</p>
                </div>
              ) : isLoadingReport ? (
                <div className="flex-1 flex flex-col items-center justify-center text-zinc-400 gap-4">
                  <div className="w-8 h-8 rounded-full border-2 border-zinc-200 border-t-zinc-900 animate-spin" />
                  <p className="text-sm">Đang tải báo cáo...</p>
                </div>
              ) : reportError ? (
                <div className="flex-1 flex flex-col items-center justify-center text-red-500 gap-4">
                  <p>{reportError}</p>
                  <button
                    onClick={() => void fetchReport(params.id)}
                    className="px-4 py-2 bg-zinc-900 text-white rounded-md hover:bg-zinc-800 transition-colors"
                  >
                    Thử lại
                  </button>
                </div>
              ) : report && report.research_task_id === params.id ? (
                <div className="flex-1 flex flex-col gap-4 text-zinc-800">
                  <div className="prose prose-zinc max-w-none">
                    <pre className="whitespace-pre-wrap font-sans text-sm">{report.content_markdown}</pre>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-zinc-400">
                  Chưa có nội dung báo cáo.
                </div>
              )}
            </Card>
          </div>

        </div>
      </div>
    </div>
  );
}

function StepItem({ title, status }: { title: string, status: 'done' | 'active' | 'waiting' }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-3 h-3 rounded-full shrink-0 ${status === 'done' ? 'bg-zinc-900' : status === 'active' ? 'bg-zinc-500 animate-pulse' : 'bg-zinc-200'}`} />
      <span className={`text-sm ${status === 'waiting' ? 'text-zinc-400' : 'text-zinc-900 font-medium'}`}>{title}</span>
    </div>
  );
}
