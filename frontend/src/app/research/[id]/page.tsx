'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { 
  ArrowLeft, CheckCircle2, Circle, Clock, Copy, Check, Download, 
  ExternalLink, FileText, Globe, Layers, Play, RefreshCw, 
  Trash2, XCircle, Search, Activity, Cpu, UploadCloud, FileUp
} from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import { Button } from '@/components/ui/Button';
import { MarkdownViewer } from '@/components/ui/MarkdownViewer';
import { api } from '@/lib/api';
import type { CitationResponse, ResearchReportResponse, ResearchSourceResponse, ResearchTaskResponse, AgentRunResponse, ArtifactItemResponse } from '@/types';

const STAGES = [
  { title: 'Lập kế hoạch', steps: ['SUPERVISOR'], statuses: ['PLANNING', 'WAITING_APPROVAL'] },
  { title: 'Thu thập và phân tích nguồn', steps: ['RESEARCHER', 'CURATOR', 'ANALYST'], statuses: ['RESEARCHING', 'INDEXING', 'ANALYZING'] },
  { title: 'Viết và phản biện', steps: ['WRITER', 'CRITIC', 'POST_PROCESSOR'], statuses: ['WRITING', 'REVIEWING', 'FINALIZING'] },
];

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW', 'PARTIAL']);

const STEP_LABELS: Record<string, string> = {
  SUPERVISOR: 'Agent lập kế hoạch',
  RESEARCHER: 'Agent tìm kiếm nguồn',
  CURATOR: 'Agent xử lý nguồn',
  ANALYST: 'Agent phân tích bằng chứng',
  WRITER: 'Agent viết báo cáo',
  CRITIC: 'Agent phản biện',
  POST_PROCESSOR: 'Đang hoàn thiện báo cáo',
};

function stageState(index: number, status: string, currentStep?: string | null): 'done' | 'active' | 'waiting' {
  if (status === 'COMPLETED') return 'done';
  const current = currentStep
    ? STAGES.findIndex(stage => stage.steps.includes(currentStep))
    : STAGES.findIndex(stage => stage.statuses.includes(status));
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

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  const [task, setTask] = useState<ResearchTaskResponse | null>(null);
  const [report, setReport] = useState<ResearchReportResponse | null>(null);
  const [citations, setCitations] = useState<CitationResponse[]>([]);
  const [sources, setSources] = useState<ResearchSourceResponse[]>([]);
  const [runs, setRuns] = useState<AgentRunResponse[]>([]);

  const [error, setError] = useState('');
  const [reportError, setReportError] = useState('');
  const [citationsError, setCitationsError] = useState('');
  const [sourcesError, setSourcesError] = useState('');
  const [runsError, setRunsError] = useState('');

  const [activeTab, setActiveTab] = useState<'report' | 'sources' | 'citations' | 'runs' | 'details'>('report');
  const [sourceSearch, setSourceSearch] = useState('');
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [isStarting, setIsStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactItemResponse[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isApprovingPlan, setIsApprovingPlan] = useState(false);
  const [isRejectingPlan, setIsRejectingPlan] = useState(false);
  const [editableQueries, setEditableQueries] = useState<string[]>([]);
  const [newQueryInput, setNewQueryInput] = useState('');
  const [planFeedback, setPlanFeedback] = useState('');

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

  const loadCitations = useCallback(async () => {
    setCitationsError('');
    try {
      const list = await api.tasks.getCitations(params.id);
      setCitations(list);
    } catch (err) {
      setCitationsError(err instanceof Error ? err.message : 'Không thể tải trích dẫn.');
    }
  }, [params.id]);

  const loadSources = useCallback(async () => {
    setSourcesError('');
    try {
      const [list, arts] = await Promise.all([
        api.tasks.getSources(params.id),
        api.tasks.getArtifacts(params.id).catch(() => []),
      ]);
      setSources(list);
      setArtifacts(arts);
    } catch (err) {
      setSourcesError(err instanceof Error ? err.message : 'Không thể tải danh sách nguồn.');
    }
  }, [params.id]);

  const loadRuns = useCallback(async () => {
    setRunsError('');
    try {
      const list = await api.tasks.getAgentRuns(params.id);
      setRuns(list);
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : 'Không thể tải lịch sử chạy của agent.');
    }
  }, [params.id]);

  useEffect(() => {
    let active = true;
    setTask(null);
    setReport(null);
    setCitations([]);
    setSources([]);
    setRuns([]);
    setError('');
    setReportError('');
    setCitationsError('');
    setSourcesError('');
    setRunsError('');

    const poll = async () => {
      try {
        const value = await api.tasks.get(params.id);
        if (!active) return;
        setTask(value);
        setError('');

        if (['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(value.status)) {
          void loadReport();
          void loadCitations();
          void loadSources();
          void loadRuns();
        } else if (value.status !== 'PENDING') {
          void loadSources();
          void loadRuns();
        }

        if (TERMINAL.has(value.status)) {
          clearInterval(timer);
        }
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Không thể tải tiến trình nghiên cứu.');
        clearInterval(timer);
      }
    };

    const timer = setInterval(() => { void poll(); }, 4000);
    void poll();
    return () => { active = false; clearInterval(timer); };
  }, [params.id, loadReport, loadCitations, loadSources, loadRuns, reloadKey]);

  const handleStartTask = async () => {
    if (!task) return;
    setIsStarting(true);
    try {
      await api.tasks.start(task.id);
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể bắt đầu nghiên cứu.');
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancelTask = async () => {
    if (!task) return;
    if (!confirm('Bạn có chắc chắn muốn hủy bài nghiên cứu này?')) return;
    setIsCancelling(true);
    try {
      await api.tasks.cancel(task.id);
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể hủy bài nghiên cứu.');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDeleteTask = async () => {
    if (!task) return;
    if (!confirm('Bạn có chắc chắn muốn xóa bài nghiên cứu này vĩnh viễn?')) return;
    setIsDeleting(true);
    try {
      await api.tasks.delete(task.id);
      router.push('/dashboard');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể xóa bài nghiên cứu.');
      setIsDeleting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !task) return;
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setUploadError('Chỉ hỗ trợ định dạng tệp tin PDF (.pdf).');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('Dung lượng tệp vượt quá giới hạn 10 MiB theo quy định hệ thống.');
      return;
    }
    setIsUploading(true);
    setUploadError('');
    setUploadSuccess(null);
    try {
      const res = await api.tasks.uploadPdf(task.id, file);
      setUploadSuccess(`Đã nạp thành công "${res.file_name}" (${res.page_count} trang, ${res.chunks_count} đoạn trích và nhúng vector).`);
      await loadSources();
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Tải lên tài liệu PDF thất bại.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownloadArtifact = async (artifactId: string, filename: string) => {
    if (!task) return;
    try {
      const token = typeof window !== 'undefined' ? sessionStorage.getItem('synthia_access_token') : null;
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const res = await fetch(`${API_BASE}/research/${task.id}/artifacts/${artifactId}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('Không thể tải xuống tài liệu');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Lỗi tải xuống');
    }
  };

  const handleCopyMarkdown = () => {
    if (!report?.content_markdown) return;
    void navigator.clipboard.writeText(report.content_markdown).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    });
  };

  const handleDownloadMarkdown = () => {
    if (!report?.content_markdown || !task) return;
    const blob = new Blob([report.content_markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${task.title.replace(/[/\\?%*:|"<>]/g, '_')}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (task?.plan?.search_queries && editableQueries.length === 0) {
      setEditableQueries(task.plan.search_queries);
    }
  }, [task?.plan, editableQueries.length]);

  const handleAddQuery = () => {
    if (!newQueryInput.trim()) return;
    setEditableQueries(prev => [...prev, newQueryInput.trim()]);
    setNewQueryInput('');
  };

  const handleRemoveQuery = (index: number) => {
    setEditableQueries(prev => prev.filter((_, i) => i !== index));
  };

  const handleApprovePlan = async () => {
    if (!task) return;
    setIsApprovingPlan(true);
    try {
      await api.tasks.approvePlan(task.id, {
        approved_queries: editableQueries.filter(q => q.trim().length > 0),
        feedback: planFeedback.trim() || undefined,
      });
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể duyệt kế hoạch.');
    } finally {
      setIsApprovingPlan(false);
    }
  };

  const handleRejectPlan = async () => {
    if (!task) return;
    const reason = prompt('Nhập lý do từ chối hoặc hướng dẫn điều chỉnh cho Supervisor:') || '';
    if (!reason.trim()) return;
    setIsRejectingPlan(true);
    try {
      await api.tasks.rejectPlan(task.id, { reason: reason.trim() });
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể từ chối kế hoạch.');
    } finally {
      setIsRejectingPlan(false);
    }
  };

  if (error) {
    return (
      <div className="p-8 text-center text-red-700" role="alert">
        {error}
        <div className="mt-4">
          <Button variant="outline" onClick={() => setReloadKey(v => v + 1)}>Thử lại</Button>
        </div>
      </div>
    );
  }

  if (!task || task.id !== params.id) {
    return <div className="p-8 text-center text-zinc-500">Đang tải bài nghiên cứu...</div>;
  }

  const isWorking = !TERMINAL.has(task.status) && task.status !== 'WAITING_APPROVAL' && task.status !== 'WAITING_USER_DATA' && task.status !== 'PENDING';
  const canCancel = !TERMINAL.has(task.status) && task.status !== 'PENDING';

  const filteredSources = sources.filter(s => 
    `${s.title ?? ''} ${s.url} ${s.content_snippet ?? ''} ${s.source_tag}`.toLowerCase().includes(sourceSearch.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-50">
      {/* Top Header Bar */}
      <div className="min-h-16 px-6 py-3 border-b border-zinc-200 bg-white flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <Link
            href="/dashboard"
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 transition-colors shrink-0"
            title="Quay lại Dashboard"
          >
            <ArrowLeft size={18} />
          </Link>
          <div>
            <h1 className="font-semibold text-lg line-clamp-1 text-zinc-900">{task.title}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-0.5 text-xs text-zinc-500">
              <span className="flex items-center gap-1.5 font-medium">
                {isWorking && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}
                {statusLabel(task.status)}
                {isWorking && task.current_step ? ` · ${STEP_LABELS[task.current_step] ?? task.current_step}` : ''}
              </span>
              <span>•</span>
              <span className="text-zinc-400">Độ sâu: {task.research_depth}</span>
              <span>•</span>
              <span className="text-zinc-400">Vòng: {task.current_iteration}/{task.max_iterations}</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {(task.status === 'PENDING' || task.status === 'CANCELLED') && (
            <Button
              variant={task.status === 'CANCELLED' ? 'primary' : 'success'}
              onClick={() => void handleStartTask()}
              isLoading={isStarting}
            >
              <Play size={15} className="mr-1.5" /> {task.status === 'CANCELLED' ? 'Chạy lại nghiên cứu' : 'Bắt đầu nghiên cứu'}
            </Button>
          )}

          {canCancel && (
            <Button variant="danger-outline" onClick={() => void handleCancelTask()} isLoading={isCancelling}>
              <XCircle size={15} className="mr-1.5" /> Hủy nghiên cứu
            </Button>
          )}

          {report && (
            <div className="hidden sm:flex items-center gap-2">
              <Button variant="outline" onClick={handleCopyMarkdown} title="Sao chép Markdown">
                {isCopied ? <Check size={15} className="text-emerald-600 mr-1.5" /> : <Copy size={15} className="mr-1.5" />}
                {isCopied ? 'Đã sao chép' : 'Sao chép'}
              </Button>
              <Button variant="outline" onClick={handleDownloadMarkdown} title="Tải file .md">
                <Download size={15} className="mr-1.5" /> Tải về
              </Button>
            </div>
          )}

          <Button variant="outline" onClick={() => setReloadKey(v => v + 1)} aria-label="Làm mới">
            <RefreshCw size={15} />
          </Button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex flex-1 overflow-hidden flex-col lg:flex-row">
        {/* Stages Sidebar */}
        <aside className="w-full lg:w-80 border-r border-zinc-200 bg-zinc-50/50 flex flex-col shrink-0 overflow-y-auto max-h-60 lg:max-h-none">
          <div className="p-4 border-b border-zinc-200">
            <h2 className="font-semibold text-xs uppercase tracking-wider text-zinc-500">Các giai đoạn nghiên cứu</h2>
          </div>
          <div className="p-4">
            <div className="relative border-l-2 border-zinc-200 ml-3 space-y-6">
              {STAGES.map((stage, index) => {
                const state = stageState(index, task.status, task.current_step);
                const Icon = state === 'done' ? CheckCircle2 : state === 'active' ? Clock : Circle;
                return (
                  <div key={stage.title} className="relative pl-6">
                    <span className={`absolute -left-3.5 top-0.5 p-1 rounded-full border border-zinc-200 bg-white ${state === 'done' ? 'text-emerald-500' : state === 'active' ? 'text-blue-500' : 'text-zinc-300'}`}>
                      <Icon size={14} />
                    </span>
                    <span className={`text-sm ${state === 'waiting' ? 'text-zinc-400' : 'font-medium text-zinc-900'}`}>
                      {stage.title}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="p-4 border-t border-zinc-200 mt-auto bg-white text-xs text-zinc-600 space-y-2.5">
            <div className="flex justify-between">
              <span className="text-zinc-500">Tokens tiêu thụ:</span>
              <strong className="font-semibold text-zinc-800">{task.total_tokens_used.toLocaleString('vi-VN')}</strong>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Chi phí ước tính:</span>
              <strong className="font-semibold text-zinc-800">${Number(task.total_cost_usd).toFixed(4)}</strong>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Kiểu trích dẫn:</span>
              <Badge variant="outline">{task.citation_style}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Cập nhật:</span>
              <span className="text-zinc-700">{formatDate(task.updated_at)}</span>
            </div>
          </div>
        </aside>

        {/* Content Tabs Area */}
        <main className="flex-1 flex flex-col bg-white overflow-hidden">
          {task.status === 'WAITING_APPROVAL' && (
            <div className="p-4 bg-amber-50/80 border-b border-amber-200 overflow-y-auto max-h-96 shrink-0">
              <div className="max-w-4xl mx-auto space-y-3.5">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="p-1.5 rounded-lg bg-amber-200 text-amber-900 shrink-0">
                      <Clock size={18} />
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-sm text-amber-950">Phê duyệt kế hoạch nghiên cứu (Human-in-the-Loop)</h2>
                        <Badge variant="outline" className="border-amber-300 bg-amber-100 text-amber-900 text-[11px]">Đang chờ phê duyệt</Badge>
                      </div>
                      <p className="text-xs text-amber-800/90 mt-0.5">
                        Supervisor Agent đã hoàn thành đề cương. Bạn có thể kiểm tra góc nhìn, tinh chỉnh từ khóa tìm kiếm trước khi các Agent thu thập dữ liệu.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                    <Button
                      variant="outline"
                      onClick={() => void handleRejectPlan()}
                      isLoading={isRejectingPlan}
                      className="h-8 px-3 text-xs border-amber-300 text-amber-900 hover:bg-amber-100/70"
                    >
                      Yêu cầu lập lại
                    </Button>
                    <Button
                      variant="primary"
                      onClick={() => void handleApprovePlan()}
                      isLoading={isApprovingPlan}
                      className="h-8 px-3 text-xs bg-amber-900 hover:bg-amber-950 text-white"
                    >
                      <Check size={14} className="mr-1.5" /> Duyệt kế hoạch & Chạy tiếp
                    </Button>
                  </div>
                </div>

                {task.plan && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    {task.plan.research_angle && (
                      <div className="p-3 bg-white rounded-xl border border-amber-200/80 shadow-2xs">
                        <span className="font-medium text-amber-950 block mb-1">Góc nhìn & Hướng tiếp cận:</span>
                        <p className="text-zinc-700 leading-relaxed">{task.plan.research_angle}</p>
                      </div>
                    )}
                    {task.plan.required_sections && Array.isArray(task.plan.required_sections) && (
                      <div className="p-3 bg-white rounded-xl border border-amber-200/80 shadow-2xs">
                        <span className="font-medium text-amber-950 block mb-1.5">Cấu trúc báo cáo dự kiến:</span>
                        <div className="flex flex-wrap gap-1.5">
                          {task.plan.required_sections.map((sec: string, idx: number) => (
                            <span key={idx} className="px-2 py-0.5 rounded bg-amber-100/70 text-amber-900 font-medium text-[11px]">
                              {sec}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="p-3 bg-white rounded-xl border border-amber-200/80 text-xs space-y-2 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-amber-950">Các truy vấn tìm kiếm Web ({editableQueries.length}):</span>
                    <span className="text-[11px] text-zinc-400">Nhấn dấu × để xóa, hoặc thêm từ khóa mới</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {editableQueries.map((query, idx) => (
                      <span key={idx} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-100 text-zinc-800 border border-zinc-200 text-xs">
                        <span>{query}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveQuery(idx)}
                          className="text-zinc-400 hover:text-red-600 font-bold ml-1 text-xs"
                          title="Xóa truy vấn"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 pt-1.5">
                    <input
                      type="text"
                      value={newQueryInput}
                      onChange={e => setNewQueryInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddQuery(); } }}
                      placeholder="Thêm từ khóa tìm kiếm mới..."
                      className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-900"
                    />
                    <Button variant="outline" className="h-8 px-3 text-xs" onClick={handleAddQuery}>
                      Thêm
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="flex border-b border-zinc-200 px-4 bg-zinc-50/80 shrink-0 gap-1 overflow-x-auto">
            <button 
              onClick={() => setActiveTab('report')} 
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${activeTab === 'report' ? 'border-zinc-900 text-zinc-900 bg-white' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
            >
              <FileText size={15} className="inline mr-1.5 opacity-70" />
              Bài báo {report ? `(${report.word_count} từ)` : ''}
            </button>
            <button 
              onClick={() => setActiveTab('sources')} 
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${activeTab === 'sources' ? 'border-zinc-900 text-zinc-900 bg-white' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
            >
              <Globe size={15} className="inline mr-1.5 opacity-70" />
              Nguồn tài liệu ({sources.length})
            </button>
            <button 
              onClick={() => setActiveTab('citations')} 
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${activeTab === 'citations' ? 'border-zinc-900 text-zinc-900 bg-white' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
            >
              <Layers size={15} className="inline mr-1.5 opacity-70" />
              Bằng chứng & Trích dẫn ({citations.length})
            </button>
            <button 
              onClick={() => setActiveTab('runs')} 
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${activeTab === 'runs' ? 'border-zinc-900 text-zinc-900 bg-white' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
            >
              <Activity size={15} className="inline mr-1.5 opacity-70" />
              Tiến trình Agent & Chi phí ({runs.length})
            </button>
            <button 
              onClick={() => setActiveTab('details')} 
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${activeTab === 'details' ? 'border-zinc-900 text-zinc-900 bg-white' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
            >
              Thông tin & Cấu hình
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 md:p-10">
            {/* TAB 1: BÁO CÁO BÀI BÁO */}
            {activeTab === 'report' && (
              <div className="max-w-4xl mx-auto">
                {['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(task.status) ? report?.research_task_id === params.id ? (
                  <div className="space-y-6">
                    {task.status !== 'COMPLETED' && (
                      <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800 flex items-center justify-between">
                        <span>{statusLabel(task.status)} — Báo cáo chưa đầy đủ do giới hạn vòng lặp hoặc tài nguyên.</span>
                        <Badge variant="outline">{task.status}</Badge>
                      </div>
                    )}

                    <div className="bg-white rounded-2xl border border-zinc-200 p-8 shadow-sm">
                      <MarkdownViewer 
                        content={report.content_markdown} 
                        onCitationClick={(label) => {
                          setHighlightedRef(label);
                          setActiveTab('citations');
                        }}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-zinc-600">
                    {reportError || 'Đang chuẩn bị bản thảo bài báo...'}
                    {reportError && <button className="underline ml-2" onClick={() => void loadReport()}>Thử lại</button>}
                  </div>
                ) : (
                  <Card className="p-8 text-center text-zinc-600 max-w-xl mx-auto space-y-4">
                    <FileText size={36} className="mx-auto text-zinc-400" />
                    <div>
                      <h3 className="font-semibold text-zinc-900 text-base">Bản thảo bài báo đang được xây dựng</h3>
                      <p className="text-sm text-zinc-500 mt-1">
                        {task.status === 'FAILED'
                          ? 'Bài nghiên cứu đã dừng do lỗi và không có bản thảo bài báo hoàn chỉnh.' 
                          : task.status === 'CANCELLED'
                          ? 'Bài nghiên cứu này đã được hủy. Bạn có thể bấm "Chạy lại nghiên cứu" để hệ thống tiếp tục thu thập và viết báo cáo.'
                          : task.status === 'PENDING'
                          ? 'Nhiệm vụ chưa bắt đầu. Nhấn "Bắt đầu nghiên cứu" ở góc trên để chạy pipeline.'
                          : 'Các agent đang thu thập tài liệu, phân tích bằng chứng và tổng hợp bài viết.'}
                      </p>
                    </div>
                    {(task.status === 'PENDING' || task.status === 'CANCELLED') && (
                      <Button variant="primary" onClick={() => void handleStartTask()} isLoading={isStarting} className="mx-auto">
                        <Play size={16} className="mr-2" /> {task.status === 'CANCELLED' ? 'Chạy lại nghiên cứu ngay' : 'Bắt đầu nghiên cứu ngay'}
                      </Button>
                    )}
                  </Card>
                )}
              </div>
            )}

            {/* TAB 2: NGUỒN TÀI LIỆU */}
            {activeTab === 'sources' && (
              <div className="max-w-4xl mx-auto space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-zinc-900">Nguồn tài liệu đã thu thập ({sources.length})</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Các website, bài báo khoa học và tài liệu được Agent tìm kiếm và lập chỉ mục.</p>
                  </div>
                  <div className="relative w-full sm:w-72">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                    <input 
                      value={sourceSearch} 
                      onChange={e => setSourceSearch(e.target.value)} 
                      placeholder="Tìm trong nguồn..." 
                      className="w-full pl-9 pr-4 py-2 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                    />
                  </div>
                </div>

                {/* PDF Ingestion Card (SRS FR-02 & Private Artifact Grounding) */}
                <Card className="p-5 border-dashed border-2 border-zinc-200 bg-zinc-50/70 hover:border-zinc-300 transition-colors">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <UploadCloud size={20} className="text-zinc-700" />
                        <h3 className="font-semibold text-sm text-zinc-900">Tải lên tài liệu PDF riêng tư (Private Grounding)</h3>
                      </div>
                      <p className="text-xs text-zinc-500 leading-relaxed">
                        Hệ thống sẽ trích xuất văn bản, băm nhỏ chunk, lập chỉ mục pgvector và tích hợp làm bằng chứng tin cậy cho AI Agents (tối đa 5 file, &lt; 20MB, &lt; 100 trang).
                      </p>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,application/pdf"
                        onChange={(e) => void handleFileUpload(e)}
                        className="hidden"
                        id="pdf-upload-input"
                        disabled={isUploading || task.status === 'COMPLETED' || task.status === 'CANCELLED'}
                      />
                      <Button
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        isLoading={isUploading}
                        disabled={task.status === 'COMPLETED' || task.status === 'CANCELLED'}
                      >
                        <FileUp size={15} className="mr-1.5" />
                        {isUploading ? 'Đang nạp PDF...' : 'Tải lên PDF'}
                      </Button>
                    </div>
                  </div>

                  {uploadError && (
                    <div className="mt-3 text-xs text-red-600 bg-red-50 p-2.5 rounded-lg border border-red-200 flex items-center justify-between">
                      <span>{uploadError}</span>
                      <button onClick={() => setUploadError('')} className="text-red-400 hover:text-red-700 ml-2">✕</button>
                    </div>
                  )}

                  {uploadSuccess && (
                    <div className="mt-3 text-xs text-emerald-700 bg-emerald-50 p-2.5 rounded-lg border border-emerald-200 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                        {uploadSuccess}
                      </span>
                      <button onClick={() => setUploadSuccess(null)} className="text-emerald-500 hover:text-emerald-800 ml-2">✕</button>
                    </div>
                  )}
                </Card>

                {sourcesError && (
                  <div className="text-sm text-red-600 bg-red-50 p-4 rounded-xl border border-red-200">
                    {sourcesError} <button className="underline ml-2" onClick={() => void loadSources()}>Thử lại</button>
                  </div>
                )}

                {sources.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {isWorking ? 'Agent đang tìm kiếm và duyệt nguồn...' : 'Chưa có nguồn tài liệu nào được lưu cho bài nghiên cứu này.'}
                  </Card>
                ) : filteredSources.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    Không tìm thấy nguồn tài liệu phù hợp với từ khóa &ldquo;{sourceSearch}&rdquo;.
                  </Card>
                ) : (
                  <div className="space-y-4">
                    {filteredSources.map((source) => (
                      <Card key={source.id} className="p-5 space-y-3 hover:border-zinc-300 transition-colors">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 border border-zinc-200">
                              [{source.source_tag}]
                            </span>
                            <Badge variant="outline">{source.source_type}</Badge>
                            {source.relevance_score > 0 && (
                              <span className="text-xs text-emerald-600 font-medium">
                                Liên quan: {(source.relevance_score * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-zinc-400">{formatDate(source.created_at)}</span>
                        </div>

                        <div>
                          {source.source_type === 'PDF' ? (
                            <div className="flex flex-col gap-2">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-base text-zinc-900">{source.title || 'Tài liệu PDF nội bộ'}</span>
                                <Badge variant="purple">Tài liệu riêng</Badge>
                              </div>
                              {(() => {
                                const matchingArt = artifacts.find(a => source.url.includes(a.file_path.split('/').pop() || '') || a.file_path.includes(source.title || ''));
                                if (matchingArt) {
                                  return (
                                    <div className="pt-1">
                                      <button
                                        type="button"
                                        onClick={() => handleDownloadArtifact(matchingArt.id, matchingArt.file_path.split('/').pop() || 'document.pdf')}
                                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 transition-colors cursor-pointer"
                                      >
                                        <Download size={13} className="text-purple-600" />
                                        <span>Tải PDF gốc ({(matchingArt.file_size_bytes / 1024 / 1024).toFixed(2)} MB)</span>
                                      </button>
                                    </div>
                                  );
                                }
                                return null;
                              })()}
                            </div>
                          ) : (
                            <a 
                              href={source.url} 
                              target="_blank" 
                              rel="noopener noreferrer" 
                              className="font-semibold text-base text-zinc-900 hover:text-blue-600 inline-flex items-center gap-1.5 transition-colors"
                            >
                              <span>{source.title || source.url}</span>
                              <ExternalLink size={14} className="shrink-0 text-zinc-400" />
                            </a>
                          )}
                          <div className="text-xs text-zinc-400 mt-1 truncate">{source.url}</div>
                        </div>

                        {source.content_snippet && (
                          <p className="text-xs leading-relaxed text-zinc-600 bg-zinc-50/80 p-3 rounded-xl border border-zinc-100 line-clamp-3">
                            {source.content_snippet}
                          </p>
                        )}

                        {source.attribution && (
                          <div className="text-xs text-zinc-500 border-t border-zinc-100 pt-2 flex items-center justify-between">
                            <span>Tác quyền: {source.attribution}</span>
                            {source.license_name && <span>Giấy phép: {source.license_name}</span>}
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: BẰNG CHỨNG & TRÍCH DẪN */}
            {activeTab === 'citations' && (
              <div className="max-w-4xl mx-auto space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-zinc-900">Bằng chứng & Trích dẫn đã xác minh ({citations.length})</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Mỗi trích dẫn được neo chặt vào đoạn trích nguồn (chunk) và luận điểm (claim) tương ứng trong bài báo.
                  </p>
                </div>

                {citationsError && (
                  <div className="text-sm text-red-600 bg-red-50 p-4 rounded-xl border border-red-200">
                    {citationsError} <button className="underline ml-2" onClick={() => void loadCitations()}>Thử lại</button>
                  </div>
                )}

                {citations.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(task.status) 
                      ? 'Chưa có trích dẫn đã xác minh cho bài này.' 
                      : 'Trích dẫn sẽ xuất hiện khi pipeline hoàn thành trích xuất bằng chứng.'}
                  </Card>
                ) : (
                  <div className="space-y-4">
                    {citations.map((citation) => {
                      const isHighlighted = highlightedRef && (citation.citation_label.includes(highlightedRef) || String(citation.citation_number) === highlightedRef);
                      return (
                        <Card 
                          key={citation.id} 
                          className={`p-5 space-y-3 transition-all ${isHighlighted ? 'ring-2 ring-blue-500 bg-blue-50/30' : 'hover:border-zinc-300'}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                              {citation.citation_label || `[${citation.citation_number ?? '?'}]`}
                            </span>
                            {citation.source_url ? (
                              <a 
                                href={citation.source_url} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="text-xs font-medium text-blue-600 hover:underline inline-flex items-center gap-1 max-w-md truncate"
                              >
                                <span className="truncate">{citation.source_title || citation.source_url}</span>
                                <ExternalLink size={12} className="shrink-0" />
                              </a>
                            ) : (
                              <span className="text-xs text-zinc-400">Không có liên kết nguồn</span>
                            )}
                          </div>

                          {citation.claim_text && (
                            <div className="text-sm text-zinc-900 font-medium">
                              <span className="text-zinc-500 font-normal">Luận điểm xác minh: </span>
                              {citation.claim_text}
                            </div>
                          )}

                          {citation.chunk_content && (
                            <blockquote className="text-xs text-zinc-700 border-l-4 border-blue-400 pl-3.5 py-2 italic bg-zinc-50 rounded-r-lg">
                              &ldquo;{citation.chunk_content}&rdquo;
                            </blockquote>
                          )}
                        </Card>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB: TIẾN TRÌNH AGENT & CHI PHÍ */}
            {activeTab === 'runs' && (
              <div className="max-w-4xl mx-auto space-y-6">
                {/* KPI Overview */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">Tổng chi phí</span>
                    <div className="text-xl font-bold text-zinc-900 font-mono">${Number(task.total_cost_usd).toFixed(4)}</div>
                    <span className="text-[11px] text-zinc-400">USD ước tính</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">Tổng Tokens</span>
                    <div className="text-xl font-bold text-zinc-900 font-mono">{task.total_tokens_used.toLocaleString('vi-VN')}</div>
                    <span className="text-[11px] text-zinc-400">Input + Output</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">Lượt chạy Agent</span>
                    <div className="text-xl font-bold text-zinc-900">{runs.length}</div>
                    <span className="text-[11px] text-zinc-400">Đã ghi nhận</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">Thời gian hoàn tất</span>
                    <div className="text-sm font-semibold text-zinc-800 line-clamp-1 mt-1">
                      {task.completed_at ? formatDate(task.completed_at) : isWorking ? 'Đang thực thi...' : 'Chưa hoàn tất'}
                    </div>
                    <span className="text-[11px] text-zinc-400">Lần chạy #{task.attempt_number}</span>
                  </div>
                </div>

                {runsError && (
                  <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
                    {runsError}
                  </div>
                )}

                {runs.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-600 max-w-xl mx-auto space-y-3">
                    <Activity size={36} className="mx-auto text-zinc-400" />
                    <div>
                      <h3 className="font-semibold text-zinc-900 text-base">Chưa có lượt chạy agent nào</h3>
                      <p className="text-sm text-zinc-500 mt-1">
                        Khi bài nghiên cứu bắt đầu chạy, tiến trình từng agent cùng token và chi phí sẽ hiển thị chi tiết tại đây.
                      </p>
                    </div>
                  </Card>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-bold text-zinc-900">Chi tiết chuỗi thực thi tác tử</h2>
                      <span className="text-xs text-zinc-500">{runs.length} tác tử</span>
                    </div>

                    <div className="relative border-l-2 border-zinc-200 ml-4 pl-6 space-y-6">
                      {runs.map((run, index) => {
                        const isSuccess = run.status === 'SUCCESS';
                        const isRunning = run.status === 'RUNNING';
                        return (
                          <div key={run.id} className="relative">
                            {/* Timeline bullet */}
                            <span className={`absolute -left-[33px] top-1.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center ${
                              isSuccess ? 'bg-emerald-500 ring-2 ring-emerald-200' : isRunning ? 'bg-blue-500 ring-2 ring-blue-200 animate-pulse' : 'bg-red-500 ring-2 ring-red-200'
                            }`} />

                            <Card className="p-5 space-y-3 hover:border-zinc-300 transition-all shadow-sm">
                              {/* Run Header */}
                              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 pb-2.5">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-sm text-zinc-900">
                                    #{index + 1} {run.agent_name}
                                  </span>
                                  <Badge variant={isSuccess ? 'success' : isRunning ? 'default' : 'danger'}>
                                    {run.status}
                                  </Badge>
                                  {run.iteration > 0 && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 font-mono">
                                      Vòng {run.iteration}
                                    </span>
                                  )}
                                </div>

                                <div className="flex items-center gap-3 text-xs text-zinc-500 font-mono">
                                  <span>{run.duration_ms >= 1000 ? `${(run.duration_ms / 1000).toFixed(2)}s` : `${run.duration_ms}ms`}</span>
                                  {run.model && (
                                    <span className="px-2 py-0.5 rounded bg-zinc-100 text-zinc-700 border border-zinc-200">
                                      {run.model}
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Token and Cost Metrics */}
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-zinc-50/70 p-2.5 rounded-lg border border-zinc-100">
                                <div>
                                  <span className="text-zinc-400">Tokens Input:</span>
                                  <div className="font-semibold text-zinc-800 font-mono">{run.input_tokens.toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-zinc-400">Tokens Output:</span>
                                  <div className="font-semibold text-zinc-800 font-mono">{run.output_tokens.toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-zinc-400">Tổng Tokens:</span>
                                  <div className="font-semibold text-zinc-800 font-mono">{(run.input_tokens + run.output_tokens).toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-zinc-400">Chi phí ước tính:</span>
                                  <div className="font-semibold text-zinc-800 font-mono">${Number(run.estimated_cost).toFixed(6)}</div>
                                </div>
                              </div>

                              {/* Summaries */}
                              {(Object.keys(run.input_summary || {}).length > 0 || Object.keys(run.output_summary || {}).length > 0) && (
                                <div className="space-y-1.5 text-xs">
                                  {Object.keys(run.output_summary || {}).length > 0 && (
                                    <div className="text-zinc-600">
                                      <span className="font-semibold text-zinc-700">Kết quả đầu ra: </span>
                                      <span className="font-mono text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">
                                        {JSON.stringify(run.output_summary)}
                                      </span>
                                    </div>
                                  )}
                                  {run.tool_calls && run.tool_calls.length > 0 && (
                                    <div className="text-zinc-600">
                                      <span className="font-semibold text-zinc-700">Công cụ đã gọi: </span>
                                      <span className="font-mono text-zinc-700">
                                        {run.tool_calls.map((tc, idx) => (
                                          <span key={idx} className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                                            {tc.tool || JSON.stringify(tc)}
                                          </span>
                                        ))}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              )}

                              {run.error_message && (
                                <div className="text-xs text-red-700 bg-red-50 p-2.5 rounded-lg border border-red-200">
                                  <strong>Lỗi: </strong>{run.error_message}
                                </div>
                              )}
                            </Card>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: THÔNG TIN & CẤU HÌNH */}
            {activeTab === 'details' && (
              <div className="max-w-4xl mx-auto space-y-6">
                <Card className="p-6 space-y-5">
                  <h2 className="text-lg font-bold text-zinc-900 border-b border-zinc-200 pb-3">Cấu hình & Chi tiết nhiệm vụ</h2>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-semibold text-zinc-700">Câu hỏi nghiên cứu:</span>
                      <p className="text-zinc-900 mt-1 leading-relaxed bg-zinc-50 p-3 rounded-xl border border-zinc-200">
                        {task.research_question}
                      </p>
                    </div>

                    <div>
                      <span className="font-semibold text-zinc-700">Mô tả bổ sung:</span>
                      <p className="text-zinc-600 mt-1 leading-relaxed bg-zinc-50 p-3 rounded-xl border border-zinc-200">
                        {task.description || 'Không có mô tả bổ sung'}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm border-t border-zinc-100 pt-4">
                    <div>
                      <span className="text-xs text-zinc-500">Độ sâu nghiên cứu</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.research_depth}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">Độ dài báo cáo</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.report_length}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">Kiểu trích dẫn</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.citation_style}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">Ngôn ngữ xuất bản</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.language.toUpperCase()}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm border-t border-zinc-100 pt-4">
                    <div>
                      <span className="text-xs text-zinc-500">Duyệt kế hoạch (HITL)</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.require_plan_approval ? 'Bật' : 'Tắt'}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">Vòng lặp tối đa</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.max_iterations}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">Nguồn tối đa</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.max_sources}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">Lần chạy thử lại</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.attempt_number}</div>
                    </div>
                  </div>

                  <div className="border-t border-zinc-100 pt-4 flex flex-wrap items-center justify-between text-xs text-zinc-500 gap-2">
                    <span>Tạo lúc: {formatDate(task.created_at)}</span>
                    {task.completed_at && <span>Hoàn thành lúc: {formatDate(task.completed_at)}</span>}
                    <Link className="underline hover:text-zinc-900" href="/dashboard">Quay lại danh sách bài</Link>
                  </div>
                </Card>

                {/* Danger Zone */}
                <div className="rounded-2xl border border-red-200 bg-red-50/50 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-red-900">Vùng nguy hiểm</h3>
                    <p className="text-xs text-red-700 mt-0.5">Xóa vĩnh viễn bài nghiên cứu này cùng toàn bộ nguồn và trích dẫn liên quan.</p>
                  </div>
                  <Button variant="danger" onClick={() => void handleDeleteTask()} isLoading={isDeleting}>
                    <Trash2 size={15} className="mr-1.5" /> Xóa bài nghiên cứu
                  </Button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
