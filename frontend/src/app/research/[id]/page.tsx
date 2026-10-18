'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { 
  ArrowLeft, CheckCircle2, Circle, Clock, Copy, Check, Download, 
  ExternalLink, FileText, Globe, Layers, Play, RefreshCw, 
  Trash2, XCircle, Search
} from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import { Button } from '@/components/ui/Button';
import { MarkdownViewer } from '@/components/ui/MarkdownViewer';
import { api } from '@/lib/api';
import type { CitationResponse, ResearchReportResponse, ResearchSourceResponse, ResearchTaskResponse } from '@/types';

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

  const [error, setError] = useState('');
  const [reportError, setReportError] = useState('');
  const [citationsError, setCitationsError] = useState('');
  const [sourcesError, setSourcesError] = useState('');

  const [activeTab, setActiveTab] = useState<'report' | 'sources' | 'citations' | 'details'>('report');
  const [sourceSearch, setSourceSearch] = useState('');
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [isStarting, setIsStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

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
      const list = await api.tasks.getSources(params.id);
      setSources(list);
    } catch (err) {
      setSourcesError(err instanceof Error ? err.message : 'Không thể tải danh sách nguồn.');
    }
  }, [params.id]);

  useEffect(() => {
    let active = true;
    setTask(null);
    setReport(null);
    setCitations([]);
    setSources([]);
    setError('');
    setReportError('');
    setCitationsError('');
    setSourcesError('');

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
        } else if (value.status !== 'PENDING') {
          void loadSources();
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
  }, [params.id, loadReport, loadCitations, loadSources, reloadKey]);

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
                          <a 
                            href={source.url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="font-semibold text-base text-zinc-900 hover:text-blue-600 inline-flex items-center gap-1.5 transition-colors"
                          >
                            <span>{source.title || source.url}</span>
                            <ExternalLink size={14} className="shrink-0 text-zinc-400" />
                          </a>
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
