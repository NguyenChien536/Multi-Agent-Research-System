'use client';
import { ResearchErrorNotice } from '@/components/ResearchErrorNotice';
import { ModelConnectionSummary } from '@/components/ModelConnectionSummary';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, CheckCircle2, Circle, Clock, Copy, Check, Download,
  ExternalLink, FileText, Globe, Layers, Play, RefreshCw,
  Trash2, XCircle, Search, Activity, Cpu, UploadCloud, FileUp, FlaskConical,
  AlertTriangle, Database, Printer, Maximize2, Minimize2, PanelLeftClose, PanelLeft, PanelRight, PanelRightClose,
  ListFilter, Bookmark, BookOpen, Package, ChevronDown, FileDown, Loader2,
  MessageSquare, History, Info
} from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import { Button } from '@/components/ui/Button';
import { MarkdownViewer, extractHeadings } from '@/components/ui/MarkdownViewer';
import { PublicationArticle, PublicationExport } from '@/components/research/PublicationPaper';
import { ManuscriptReadiness } from '@/components/research/ManuscriptReadiness';
import { useLanguage } from '@/lib/i18n';
import { exportPaperToDocx } from '@/lib/docxExport';
import { stageState } from '@/lib/monitoring';
import { withoutRepeatedTitle } from '@/lib/paperPresentation';
import { api } from '@/lib/api';
import type {
  CitationResponse, ResearchReportResponse, ResearchSourceResponse,
  ResearchTaskResponse, AgentRunResponse, ArtifactItemResponse, ProtocolResponse,
  AnalysisRunResponse, ExperimentJournalEntryResponse
} from '@/types';

interface StageConfig {
  title_en: string;
  title_vi: string;
  steps: string[];
  statuses: string[];
}

const BASE_STAGES: StageConfig[] = [
  { title_en: 'Planning', title_vi: 'Lập kế hoạch', steps: ['SUPERVISOR'], statuses: ['PLANNING', 'WAITING_APPROVAL'] },
  { title_en: 'Literature Search & Analysis', title_vi: 'Thu thập và phân tích nguồn', steps: ['RESEARCHER', 'CURATOR', 'ANALYST'], statuses: ['RESEARCHING', 'INDEXING', 'ANALYZING'] },
  { title_en: 'Methodology Design', title_vi: 'Thiết kế phương pháp', steps: ['METHODOLOGIST'], statuses: ['WAITING_USER_DATA'] },
  { title_en: 'Drafting & AI Critique', title_vi: 'Viết và phản biện', steps: ['WRITER', 'CRITIC', 'POST_PROCESSOR'], statuses: ['WRITING', 'REVIEWING', 'FINALIZING'] },
];

const COMPUTATIONAL_STAGES: StageConfig[] = [
  { title_en: 'Planning', title_vi: 'Lập kế hoạch', steps: ['SUPERVISOR'], statuses: ['PLANNING', 'WAITING_APPROVAL'] },
  { title_en: 'Literature Search & Analysis', title_vi: 'Thu thập và phân tích nguồn', steps: ['RESEARCHER', 'CURATOR', 'ANALYST'], statuses: ['RESEARCHING', 'INDEXING', 'ANALYZING'] },
  { title_en: 'Methodology Design', title_vi: 'Thiết kế phương pháp', steps: ['METHODOLOGIST'], statuses: ['RUNNING'] },
  { title_en: 'Computational Routine', title_vi: 'Thực nghiệm tính toán', steps: ['EXPERIMENT_RUNNER'], statuses: ['RUNNING'] },
  { title_en: 'Drafting & AI Critique', title_vi: 'Viết và phản biện', steps: ['WRITER', 'CRITIC', 'POST_PROCESSOR'], statuses: ['WRITING', 'REVIEWING', 'FINALIZING'] },
];

const REVIEW_STAGES: StageConfig[] = [
  { title_en: 'Planning', title_vi: 'Lập kế hoạch', steps: ['SUPERVISOR'], statuses: ['PLANNING', 'WAITING_APPROVAL'] },
  { title_en: 'Literature Search & Analysis', title_vi: 'Thu thập và phân tích nguồn', steps: ['RESEARCHER', 'CURATOR', 'ANALYST'], statuses: ['RESEARCHING', 'INDEXING', 'ANALYZING'] },
  { title_en: 'Drafting & AI Critique', title_vi: 'Viết và phản biện', steps: ['WRITER', 'CRITIC', 'POST_PROCESSOR'], statuses: ['WRITING', 'REVIEWING', 'FINALIZING'] },
];

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW', 'PARTIAL']);

const OUTPUT_LANG_NAMES: Record<string, { en: string; vi: string }> = {
  en: { en: 'English', vi: 'Tiếng Anh' },
  vi: { en: 'Vietnamese', vi: 'Tiếng Việt' },
  ja: { en: 'Japanese', vi: 'Tiếng Nhật' },
  zh: { en: 'Chinese', vi: 'Tiếng Trung' },
  fr: { en: 'French', vi: 'Tiếng Pháp' },
  de: { en: 'German', vi: 'Tiếng Đức' },
  es: { en: 'Spanish', vi: 'Tiếng Tây Ban Nha' },
  ko: { en: 'Korean', vi: 'Tiếng Hàn' },
};

const STEP_LABELS_EN: Record<string, string> = {
  SUPERVISOR: 'Planning Agent (Supervisor)',
  RESEARCHER: 'Literature Search Agent (Researcher)',
  CURATOR: 'Source Indexing Agent (Curator)',
  ANALYST: 'Evidence Analysis Agent (Analyst)',
  METHODOLOGIST: 'Methodology & Protocol Agent',
  EXPERIMENT_RUNNER: 'Computational Routine Agent (Ridge & Baseline)',
  WRITER: 'Report Drafting Agent (Writer)',
  CRITIC: 'Internal AI Critic',
  POST_PROCESSOR: 'Finalizing & Citations Agent',
};

const STEP_LABELS_VI: Record<string, string> = {
  SUPERVISOR: 'Agent lập kế hoạch',
  RESEARCHER: 'Agent tìm kiếm nguồn',
  CURATOR: 'Agent xử lý nguồn',
  ANALYST: 'Agent phân tích bằng chứng',
  METHODOLOGIST: 'Agent phương pháp luận & đề cương',
  EXPERIMENT_RUNNER: 'Agent thực nghiệm tính toán (Ridge & Baseline)',
  WRITER: 'Agent viết báo cáo',
  CRITIC: 'Agent phản biện',
  POST_PROCESSOR: 'Đang hoàn thiện báo cáo',
};

function stepLabel(step: string, lang: 'en' | 'vi' = 'en'): string {
  const dict = lang === 'en' ? STEP_LABELS_EN : STEP_LABELS_VI;
  return dict[step] || step;
}

function statusLabel(status: string, lang: 'en' | 'vi' = 'en') {
  const labels_en: Record<string, string> = {
    PENDING: 'Pending', QUEUED: 'Queued', PLANNING: 'Planning',
    WAITING_APPROVAL: 'Awaiting Plan Approval', WAITING_USER_DATA: 'Awaiting Field Data',
    RESEARCHING: 'Searching Literature', INDEXING: 'Processing Sources', ANALYZING: 'Analyzing Evidence',
    WRITING: 'Drafting Paper', REVIEWING: 'AI Critique', FINALIZING: 'Finalizing Report',
    RETRYING: 'Retrying', COMPLETED: 'Completed', PARTIAL: 'Partial Result',
    NEEDS_REVIEW: 'Needs Review', FAILED: 'Failed', CANCELLED: 'Cancelled',
  };
  const labels_vi: Record<string, string> = {
    PENDING: 'Chưa bắt đầu', QUEUED: 'Đang chờ chạy', PLANNING: 'Đang lập kế hoạch',
    WAITING_APPROVAL: 'Chờ duyệt kế hoạch', WAITING_USER_DATA: 'Chờ dữ liệu',
    RESEARCHING: 'Đang tìm nguồn', INDEXING: 'Đang lập chỉ mục', ANALYZING: 'Đang phân tích',
    WRITING: 'Đang viết', REVIEWING: 'Đang phản biện', FINALIZING: 'Đang hoàn thiện',
    RETRYING: 'Đang thử lại', COMPLETED: 'Hoàn thành', PARTIAL: 'Bản nháp chưa đầy đủ',
    NEEDS_REVIEW: 'Cần xem xét', FAILED: 'Thất bại', CANCELLED: 'Đã hủy',
  };
  const labels = lang === 'en' ? labels_en : labels_vi;
  return labels[status] ?? status;
}

function formatDate(value: string, lang: 'en' | 'vi' = 'en') {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return lang === 'en' ? 'Unknown' : 'Không rõ';
  return new Intl.DateTimeFormat(lang === 'en' ? 'en-US' : 'vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { language, t } = useLanguage();
  const isEn = language === 'en';

  const [task, setTask] = useState<ResearchTaskResponse | null>(null);
  const [report, setReport] = useState<ResearchReportResponse | null>(null);
  const [citations, setCitations] = useState<CitationResponse[]>([]);
  const [sources, setSources] = useState<ResearchSourceResponse[]>([]);
  const [runs, setRuns] = useState<AgentRunResponse[]>([]);

  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState<number | null>(null);
  const [reportError, setReportError] = useState('');
  const [citationsError, setCitationsError] = useState('');
  const [sourcesError, setSourcesError] = useState('');
  const [runsError, setRunsError] = useState('');

  const [activeTab, setActiveTab] = useState<'report' | 'sources' | 'citations' | 'runs' | 'details' | 'protocol' | 'experiments'>('report');
  const [sourceSearch, setSourceSearch] = useState('');
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [isStarting, setIsStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isWidePaper, setIsWidePaper] = useState(false);
  const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false);
  const [isRightSidebarCollapsed, setIsRightSidebarCollapsed] = useState(false);

  const handleToggleWidePaper = useCallback(() => {
    setIsWidePaper(prev => {
      const next = !prev;
      if (next) {
        setIsLeftSidebarCollapsed(true);
        setIsRightSidebarCollapsed(true);
      } else {
        setIsLeftSidebarCollapsed(false);
        setIsRightSidebarCollapsed(false);
      }
      return next;
    });
  }, []);
  const [isDownloadMenuOpen, setIsDownloadMenuOpen] = useState(false);
  const [isExportingDocx, setIsExportingDocx] = useState(false);
  const [activeTocSlug, setActiveTocSlug] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactItemResponse[]>([]);
  const [retryingSourceId, setRetryingSourceId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [experiments, setExperiments] = useState<AnalysisRunResponse[]>([]);
  const [journal, setJournal] = useState<ExperimentJournalEntryResponse[]>([]);
  const [isUploadingDataset, setIsUploadingDataset] = useState(false);
  const [datasetUploadError, setDatasetUploadError] = useState('');
  const [datasetUploadSuccess, setDatasetUploadSuccess] = useState<string | null>(null);
  const datasetFileInputRef = useRef<HTMLInputElement>(null);

  const [isApprovingPlan, setIsApprovingPlan] = useState(false);
  const [isRejectingPlan, setIsRejectingPlan] = useState(false);
  const [editableQueries, setEditableQueries] = useState<string[]>([]);
  const [newQueryInput, setNewQueryInput] = useState('');
  const [planFeedback, setPlanFeedback] = useState('');

  const [protocol, setProtocol] = useState<ProtocolResponse | null>(null);
  const [protocolError, setProtocolError] = useState('');
  const [isResumingData, setIsResumingData] = useState(false);
  const [sampleSize, setSampleSize] = useState('');
  const [methodNotes, setMethodNotes] = useState('');
  const [resultsSummary, setResultsSummary] = useState('');
  const [dataProvenance, setDataProvenance] = useState('');
  const [resultArtifactId, setResultArtifactId] = useState('');
  const [isUploadingResult, setIsUploadingResult] = useState(false);
  const [resultFileError, setResultFileError] = useState('');

  const handleUploadResult = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !task) return;
    setResultFileError('');
    if (!/\.(csv|txt)$/i.test(file.name) || file.size > 5 * 1024 * 1024 || !file.size) {
      setResultFileError(isEn ? 'Select a CSV or UTF-8 TXT file with data, up to 5 MiB.' : 'Chọn CSV hoặc TXT UTF-8 có dữ liệu, tối đa 5 MiB.');
      e.target.value = '';
      return;
    }
    setIsUploadingResult(true);
    try {
      const uploaded = await api.tasks.uploadFieldworkResult(task.id, file);
      const updatedArtifacts = await api.tasks.getArtifacts(task.id);
      setArtifacts(updatedArtifacts);
      setResultArtifactId(uploaded.artifact_id);
    } catch (err) {
      setResultFileError(err instanceof Error ? err.message : (isEn ? 'Unable to load result file.' : 'Không thể tải tệp kết quả.'));
    } finally {
      setIsUploadingResult(false);
      e.target.value = '';
    }
  };

  const loadExperiments = useCallback(async () => {
    try {
      const list = await api.tasks.getExperiments(params.id);
      setExperiments(list);
    } catch {
      // ignore
    }
  }, [params.id]);

  const loadJournal = useCallback(async () => {
    try {
      const list = await api.tasks.getJournal(params.id);
      setJournal(list);
    } catch {
      // ignore
    }
  }, [params.id]);

  const handleUploadDataset = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setDatasetUploadError(isEn ? 'Only .csv format is supported.' : 'Chỉ chấp nhận tệp định dạng .csv');
      return;
    }
    setIsUploadingDataset(true);
    setDatasetUploadError('');
    setDatasetUploadSuccess(null);
    try {
      const res = await api.tasks.uploadDataset(params.id, file);
      setDatasetUploadSuccess(isEn ? `Uploaded successfully: ${res.file_name} (${res.rows_count} rows, ${res.columns_count} columns)` : `Đã tải lên thành công: ${res.file_name} (${res.rows_count} dòng, ${res.columns_count} cột)`);
      void loadSources();
      void loadExperiments();
      setReloadKey(v => v + 1);
    } catch (err) {
      setDatasetUploadError(err instanceof Error ? err.message : (isEn ? 'Dataset upload failed.' : 'Tải lên dataset thất bại'));
    } finally {
      setIsUploadingDataset(false);
      if (datasetFileInputRef.current) datasetFileInputRef.current.value = '';
    }
  };

  const loadProtocol = useCallback(async () => {
    setProtocolError('');
    try {
      const res = await api.tasks.getProtocol(params.id);
      setProtocol(res);
    } catch (err) {
      setProtocolError(err instanceof Error ? err.message : (isEn ? 'Unable to load study protocol.' : 'Không thể tải đề cương nghiên cứu.'));
    }
  }, [params.id, isEn]);

  const loadReport = useCallback(async () => {
    setReportError('');
    try {
      const value = await api.tasks.getReport(params.id);
      if (value.research_task_id === params.id) setReport(value);
      else setReportError(isEn ? 'Report does not match this research project.' : 'Báo cáo không khớp bài nghiên cứu này.');
    } catch (err) {
      setReportError(err instanceof Error ? err.message : (isEn ? 'Unable to load report.' : 'Không thể tải báo cáo.'));
    }
  }, [params.id, isEn]);

  const loadCitations = useCallback(async () => {
    setCitationsError('');
    try {
      const list = await api.tasks.getCitations(params.id);
      setCitations(list);
    } catch (err) {
      setCitationsError(err instanceof Error ? err.message : (isEn ? 'Unable to load citations.' : 'Không thể tải trích dẫn.'));
    }
  }, [params.id, isEn]);

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
      setSourcesError(err instanceof Error ? err.message : (isEn ? 'Unable to load sources.' : 'Không thể tải danh sách nguồn.'));
    }
  }, [params.id, isEn]);

  const loadRuns = useCallback(async () => {
    setRunsError('');
    try {
      const list = await api.tasks.getAgentRuns(params.id);
      setRuns(list);
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : (isEn ? 'Unable to load agent execution history.' : 'Không thể tải lịch sử chạy của agent.'));
    }
  }, [params.id, isEn]);

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

        if (['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW', 'FAILED', 'CANCELLED'].includes(value.status)) {
          void loadReport();
          void loadCitations();
          void loadSources();
          void loadRuns();
          if (value.protocol_artifact_id) void loadProtocol();
          if (value.research_type === 'EMPIRICAL_COMPUTATIONAL') {
            void loadExperiments();
            void loadJournal();
          }
        } else if (value.status !== 'PENDING') {
          void loadSources();
          void loadRuns();
          if (value.status === 'WAITING_USER_DATA' || value.protocol_artifact_id) {
            void loadProtocol();
          }
          if (value.research_type === 'EMPIRICAL_COMPUTATIONAL') {
            void loadExperiments();
            void loadJournal();
          }
        } else if (value.research_type === 'EMPIRICAL_COMPUTATIONAL') {
          void loadSources();
          void loadExperiments();
          void loadJournal();
        }

        if (TERMINAL.has(value.status)) {
          clearInterval(timer);
        }
      } catch (err) {
        if (!active) return;
        const status = err && typeof err === 'object' && 'status' in err ? (err as { status?: number }).status : null;
        setErrorCode(status ?? null);
        setError(err instanceof Error ? err.message : (isEn ? 'Unable to load research progress.' : 'Không thể tải tiến trình nghiên cứu.'));
        clearInterval(timer);
      }
    };

    const timer = setInterval(() => { void poll(); }, 4000);
    void poll();
    return () => { active = false; clearInterval(timer); };
  }, [params.id, loadReport, loadCitations, loadSources, loadRuns, loadProtocol, loadExperiments, loadJournal, reloadKey, isEn]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab') as 'report' | 'sources' | 'citations' | 'runs' | 'details' | 'protocol' | 'experiments' | null;
    if (tabParam && ['report', 'sources', 'citations', 'runs', 'details', 'protocol', 'experiments'].includes(tabParam)) {
      setActiveTab(tabParam);
    }
    const hash = window.location.hash;
    if (hash) {
      setTimeout(() => {
        const el = document.querySelector(hash);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 150);
    }
  }, [task?.status]);

  const handleStartTask = async () => {
    if (!task) return;
    setIsStarting(true);
    try {
      await api.tasks.start(task.id);
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Unable to start research.' : 'Không thể bắt đầu nghiên cứu.'));
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancelTask = async () => {
    if (!task) return;
    if (!confirm(isEn ? 'Are you sure you want to cancel this research task?' : 'Bạn có chắc chắn muốn hủy bài nghiên cứu này?')) return;
    setIsCancelling(true);
    try {
      await api.tasks.cancel(task.id);
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Unable to cancel research.' : 'Không thể hủy bài nghiên cứu.'));
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDeleteTask = async () => {
    if (!task) return;
    if (!confirm(isEn ? 'Are you sure you want to permanently delete this research project?' : 'Bạn có chắc chắn muốn xóa bài nghiên cứu này vĩnh viễn?')) return;
    setIsDeleting(true);
    try {
      await api.tasks.delete(task.id);
      router.push('/dashboard');
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Unable to delete research project.' : 'Không thể xóa bài nghiên cứu.'));
      setIsDeleting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !task) return;
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setUploadError(isEn ? 'Only PDF (.pdf) files are supported.' : 'Chỉ hỗ trợ định dạng tệp tin PDF (.pdf).');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError(isEn ? 'File size exceeds 10 MiB limit.' : 'Dung lượng tệp vượt quá giới hạn 10 MiB theo quy định hệ thống.');
      return;
    }
    setIsUploading(true);
    setUploadError('');
    setUploadSuccess(null);
    try {
      const res = await api.tasks.uploadPdf(task.id, file);
      setUploadSuccess(isEn ? `Successfully loaded "${res.file_name}" (${res.page_count} pages, ${res.chunks_count} chunks embedded).` : `Đã nạp thành công "${res.file_name}" (${res.page_count} trang, ${res.chunks_count} đoạn trích và nhúng vector).`);
      await loadSources();
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : (isEn ? 'PDF upload failed.' : 'Tải lên tài liệu PDF thất bại.'));
    } finally {
      setIsUploading(false);
    }
  };

  const handleRetrySource = async (sourceId: string) => {
    if (!task) return;
    setRetryingSourceId(sourceId);
    try {
      await api.tasks.retrySource(task.id, sourceId);
      await loadSources();
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Failed to retry ingestion' : 'Không thể thử lại trích xuất'));
    } finally {
      setRetryingSourceId(null);
    }
  };

  const handleDownloadArtifact = async (artifactId: string, filename: string) => {
    if (!task) return;
    try {
      const blob = await api.tasks.downloadArtifact(task.id, artifactId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Download error' : 'Lỗi tải xuống'));
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

  const handleDownloadBundle = () => {
    if (!report?.content_markdown || !task) return;
    const bundle = {
      task: {
        id: task.id,
        title: task.title,
        research_question: task.research_question,
        research_type: task.research_type,
        research_depth: task.research_depth,
        citation_style: task.citation_style,
        total_tokens_used: task.total_tokens_used,
        total_cost_usd: task.total_cost_usd,
        created_at: task.created_at,
        completed_at: task.completed_at,
      },
      report: {
        title: report.title,
        word_count: report.word_count,
        content_markdown: report.content_markdown,
      },
      sources: sources.map(s => ({
        source_tag: s.source_tag,
        title: s.title,
        url: s.url,
        source_type: s.source_type,
        relevance_score: s.relevance_score,
        attribution: s.attribution,
      })),
      citations: citations.map(c => ({
        citation_label: c.citation_label,
        claim_text: c.claim_text,
        chunk_content: c.chunk_content,
        source_url: c.source_url,
        source_title: c.source_title,
      })),
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${task.title.replace(/[/\\?%*:|"<>]/g, '_')}_package.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleDownloadDocx = async () => {
    if (!report?.content_markdown || !task) return;
    try {
      setIsExportingDocx(true);
      await exportPaperToDocx({
        title: report.title,
        markdownContent: report.content_markdown,
        completedAt: formatDate(report.created_at),
        researchType: task.research_type,
        filename: task.title
      });
    } catch (err) {
      console.error('Docx export error:', err);
      alert(isEn ? 'Unable to generate Word file (.docx). Please try again or download Markdown.' : 'Không thể tạo file Word (.docx). Vui lòng thử lại hoặc tải tệp Markdown.');
    } finally {
      setIsExportingDocx(false);
    }
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
        plan_version: task.plan_version,
        approved_queries: editableQueries.filter(q => q.trim().length > 0),
        feedback: planFeedback.trim() || undefined,
      });
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Unable to approve research plan.' : 'Không thể duyệt kế hoạch.'));
    } finally {
      setIsApprovingPlan(false);
    }
  };

  const handleRejectPlan = async () => {
    if (!task) return;
    const reason = prompt(isEn ? 'Enter revision instructions or feedback for the Supervisor Agent:' : 'Nhập lý do từ chối hoặc hướng dẫn điều chỉnh cho Supervisor:') || '';
    if (!reason.trim()) return;
    setIsRejectingPlan(true);
    try {
      await api.tasks.rejectPlan(task.id, { plan_version: task.plan_version, reason: reason.trim() });
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Unable to reject research plan.' : 'Không thể từ chối kế hoạch.'));
    } finally {
      setIsRejectingPlan(false);
    }
  };

  const handleResumeWithData = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task) return;
    const parsedSize = Number(sampleSize.trim());
    if (!Number.isSafeInteger(parsedSize) || parsedSize < 1) {
      alert(isEn ? 'Please enter a valid sample size (integer >= 1).' : 'Vui lòng nhập cỡ mẫu thực tế hợp lệ (số nguyên lớn hơn hoặc bằng 1).');
      return;
    }
    if (methodNotes.trim().length < 10) {
      alert(isEn ? 'Please describe data collection methodology and procedures (at least 10 characters).' : 'Vui lòng mô tả phương pháp và quy trình thu thập dữ liệu (tối thiểu 10 ký tự).');
      return;
    }
    if (resultsSummary.trim().length < 10) {
      alert(isEn ? 'Please summarize empirical findings / collected data (at least 10 characters).' : 'Vui lòng nhập tóm tắt kết quả thực nghiệm / thực địa (tối thiểu 10 ký tự).');
      return;
    }
    if (!resultArtifactId || dataProvenance.trim().length < 10 || isUploadingResult) {
      setResultFileError(isEn ? 'Select an uploaded result file and describe data provenance (at least 10 characters).' : 'Chọn tệp kết quả đã tải lên và mô tả nguồn gốc dữ liệu (ít nhất 10 ký tự).');
      return;
    }
    setIsResumingData(true);
    try {
      await api.tasks.resumeWithData(task.id, {
        plan_version: task.plan_version,
        sample_size: parsedSize,
        method_notes: methodNotes.trim(),
        results_summary: resultsSummary.trim(),
        data_provenance: dataProvenance.trim(),
        file_artifact_id: resultArtifactId,
      });
      setReloadKey(v => v + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : (isEn ? 'Unable to resume research.' : 'Không thể tiếp tục bài nghiên cứu.'));
    } finally {
      setIsResumingData(false);
    }
  };

  if (error && !task) {
    const is404 = errorCode === 404;
    const is401 = errorCode === 401;
    const is403 = errorCode === 403;
    const isAuthError = is401 || is403;
    return (
      <div className="flex flex-col items-center justify-center gap-6 p-12 sm:p-20 text-center min-h-[60vh]">
        <div className="w-16 h-16 rounded-2xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
          <FileText size={28} className="text-zinc-400" />
        </div>
        <div className="max-w-md space-y-2">
          <h2 className="text-lg font-semibold text-zinc-900">
            {is404
              ? (isEn ? 'Research project not found' : 'Không tìm thấy bài nghiên cứu')
              : is401
              ? (isEn ? 'Session expired' : 'Phiên đăng nhập đã hết hạn')
              : is403
              ? (isEn ? 'Access denied' : 'Không có quyền truy cập')
              : (isEn ? 'Failed to load project' : 'Không thể tải bài nghiên cứu')}
          </h2>
          <p className="text-sm text-zinc-500 leading-relaxed">
            {is404
              ? (isEn ? 'This project may have been deleted or the link is outdated.' : 'Dự án có thể đã bị xoá hoặc đường dẫn không còn hợp lệ.')
              : is401
              ? (isEn ? 'Your session has expired. Please sign in again.' : 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
              : is403
              ? (isEn ? 'You do not have permission to view this project.' : 'Bạn không có quyền xem dự án này.')
              : error}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          {isAuthError
            ? <Button variant="primary" onClick={() => router.push('/login')}>{isEn ? 'Sign in again' : 'Đăng nhập lại'}</Button>
            : <Button variant="primary" onClick={() => router.push('/dashboard')}>{isEn ? 'Go to Dashboard' : 'Về Dashboard'}</Button>}
          {!isAuthError && (
            <Button variant="outline" onClick={() => setReloadKey(v => v + 1)}>{isEn ? 'Retry' : 'Thử lại'}</Button>
          )}
        </div>
      </div>
    );
  }

  if (!task || task.id !== params.id) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12 sm:p-20 text-center min-h-[60vh]">
        <RefreshCw size={24} className="animate-spin text-blue-600" />
        <p className="text-sm text-zinc-500">{isEn ? 'Loading research project...' : 'Đang tải bài nghiên cứu...'}</p>
      </div>
    );
  }

    const isWorking = !TERMINAL.has(task.status) && task.status !== 'WAITING_APPROVAL' && task.status !== 'WAITING_USER_DATA' && task.status !== 'PENDING';
  const canCancel = !TERMINAL.has(task.status) && task.status !== 'PENDING';

  const filteredSources = sources.filter(s =>
    `${s.title ?? ''} ${s.url} ${s.content_snippet ?? ''} ${s.source_tag}`.toLowerCase().includes(sourceSearch.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-50 print:h-auto print:overflow-visible print:bg-white print:block">
      {/* Top Header Bar */}
      <div id="research-header-bar" className="min-h-16 px-6 py-3 border-b border-zinc-200 bg-white flex flex-wrap items-center justify-between gap-3 shrink-0 print:hidden">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <button
            type="button"
            onClick={() => setIsLeftSidebarCollapsed(prev => !prev)}
            className="hidden lg:flex items-center justify-center p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 transition-colors shrink-0"
            title={isLeftSidebarCollapsed ? (isEn ? "Show table of contents" : "Hiện mục lục bài báo") : (isEn ? "Collapse table of contents" : "Thu gọn mục lục")}
          >
            {isLeftSidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>
          <div>
            <h1 className="font-semibold text-lg line-clamp-1 text-zinc-900">{task.title}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-0.5 text-xs font-medium">
              {/* Status pill — colored by state */}
              {task.status === 'QUEUED' ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-zinc-100 border border-zinc-300 text-zinc-700 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-pulse" />
                  {isEn ? 'Queued \u2014 waiting to start' : '\u0110ang ch\u1edd ch\u1ea1y'}
                </span>
              ) : task.status === 'PLANNING' ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-blue-800 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                  {isEn ? 'Planning \u2014 AI agents initializing' : '\u0110ang l\u1eadp k\u1ebf ho\u1ea1ch'}
                </span>
              ) : task.status === 'WAITING_APPROVAL' ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-300 text-amber-900 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                  {isEn ? 'Awaiting your approval \u2193' : 'Ch\u1edd ph\xea duy\u1ec7t \u2193'}
                </span>
              ) : task.status === 'WAITING_USER_DATA' ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-300 text-amber-900 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                  {isEn ? 'Awaiting field data upload \u2193' : 'Ch\u1edd t\u1ea3i l\xean d\u1eef li\u1ec7u \u2193'}
                </span>
              ) : isWorking ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-blue-800 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                  {statusLabel(task.status, language)}
                  {task.current_step ? ` \xb7 ${stepLabel(task.current_step, language)}` : ''}
                </span>
              ) : (
                <span className="font-semibold text-zinc-800">
                  {statusLabel(task.status, language)}
                </span>
              )}
              <span className="text-zinc-400">·</span>
              <span className="text-zinc-600">{isEn ? "Depth: " : "\u0110\u1ed9 s\xe2u: "}{task.research_depth}</span>
              <span className="text-zinc-400">·</span>
              <span className="text-zinc-600">{isEn ? "Iteration: " : "V\xf2ng: "}{task.current_iteration}/{task.max_iterations}</span>
              {task.language && (
                <>
                  <span className="text-zinc-400">·</span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200">
                    {isEn ? 'Output: ' : 'Ng\xf4n ng\u1eef: '}{OUTPUT_LANG_NAMES[task.language]?.[language as 'en' | 'vi'] || task.language.toUpperCase()}
                  </span>
                </>
              )}
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
              <Play size={15} className="mr-1.5" /> {task.status === 'CANCELLED' ? (isEn ? 'Rerun Research' : 'Chạy lại nghiên cứu') : (isEn ? 'Start Research' : 'Bắt đầu nghiên cứu')}
            </Button>
          )}

          {canCancel && (
            <Button variant="danger-outline" onClick={() => void handleCancelTask()} isLoading={isCancelling}>
              <XCircle size={15} className="mr-1.5" /> {isEn ? 'Cancel Research' : 'Hủy nghiên cứu'}
            </Button>
          )}


          <Button variant="outline" onClick={() => setReloadKey(v => v + 1)} aria-label={isEn ? "Refresh" : "Làm mới"}>
            <RefreshCw size={15} />
          </Button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex flex-1 overflow-hidden flex-col lg:flex-row print:overflow-visible print:h-auto print:block">
        {/* Stages Sidebar */}
        {/* Left Sidebar: Table of Contents & Manuscript Details */}
        <aside id="toc-sidebar" className={`${isLeftSidebarCollapsed ? 'hidden' : 'w-full lg:w-72 xl:w-80'} border-r border-zinc-200 bg-zinc-50/70 flex flex-col shrink-0 overflow-y-auto max-h-72 lg:max-h-none transition-all duration-200 print:hidden`}>
          <div className="p-4 border-b border-zinc-200 flex items-center justify-between sticky top-0 bg-zinc-50/95 backdrop-blur z-10">
            <div className="flex items-center gap-2">
              <ListFilter size={17} className="text-zinc-700" />
              <h2 className="font-bold text-sm sm:text-base uppercase tracking-wider text-zinc-900">
                {isEn ? "Table of Contents" : "Mục lục bài báo"}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setIsLeftSidebarCollapsed(true)}
              className="hidden lg:block text-zinc-400 hover:text-zinc-700 transition-colors p-1.5 rounded-lg hover:bg-zinc-200/60"
              title={isEn ? "Collapse table of contents" : "Thu gọn mục lục"}
            >
              <PanelLeftClose size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-zinc-200">
            {/* Table of Contents Section */}
            {(() => {
              const headings = report ? extractHeadings(withoutRepeatedTitle(report.content_markdown, report.title)) : [];
              if (headings.length > 0) {
                return (
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-2 px-1">
                      <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                        {isEn ? "Sections" : "Các đề mục"}
                      </span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-800 font-bold">
                        {headings.length} {isEn ? "parts" : "mục"}
                      </span>
                    </div>
                    <nav className="space-y-1 text-xs">
                      {headings.map((h, i) => (
                        <a
                          key={i}
                          href={`#${h.slug}`}
                          onClick={(e) => {
                            e.preventDefault();
                            if (activeTab !== 'report') setActiveTab('report');
                            setTimeout(() => {
                              const el = document.getElementById(h.slug);
                              if (el) {
                                el.scrollIntoView({ behavior: 'smooth' });
                                setActiveTocSlug(h.slug);
                              }
                            }, 50);
                          }}
                          className={`block py-1.5 px-2.5 rounded-lg transition-colors truncate ${
                            h.level === 1 ? 'font-bold text-zinc-900 text-xs' :
                            h.level === 2 ? 'pl-4 font-semibold text-zinc-700 text-xs' :
                            'pl-6 text-zinc-500 text-[11px]'
                          } hover:bg-zinc-200/70 hover:text-zinc-950 ${activeTocSlug === h.slug ? 'bg-white shadow-xs text-zinc-950 font-bold border-l-2 border-zinc-900' : ''}`}
                          title={h.title}
                        >
                          {h.title}
                        </a>
                      ))}
                    </nav>
                  </div>
                );
              }
              return (
                <div className="p-4 text-xs text-zinc-500 leading-relaxed italic">
                  {report
                    ? (isEn ? "Draft contains no section headings." : "Bản thảo chưa phân mục.")
                    : (isEn ? "Table of contents will appear once manuscript draft is generated." : "Mục lục sẽ hiển thị khi bản thảo bài báo được tạo.")
                  }
                </div>
              );
            })()}

            {/* Draft Details (Thông tin bản thảo) */}
            <div className="p-4 space-y-3.5 text-xs">
              <div className="flex items-center gap-1.5 pb-2 border-b border-zinc-200">
                <Bookmark size={15} className="text-zinc-700" />
                <h3 className="font-bold text-xs uppercase tracking-wider text-zinc-900">
                  {isEn ? "Draft Details" : "Thông tin bản thảo"}
                </h3>
              </div>

              {report && (
                <div className="space-y-2.5 text-zinc-700">
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-500">{isEn ? "Word count:" : "Số lượng từ:"}</span>
                    <strong className="font-bold text-zinc-900 font-mono text-xs">{report.word_count.toLocaleString()} {isEn ? "words" : "từ"}</strong>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-500">{isEn ? "Reading time:" : "Thời gian đọc:"}</span>
                    <strong className="font-bold text-zinc-900 font-mono text-xs">~{Math.max(1, Math.ceil((report.word_count || 1) / 220))} {isEn ? "min" : "phút"}</strong>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-500">{isEn ? "Sources cited:" : "Nguồn tài liệu:"}</span>
                    <span className="font-bold text-zinc-900">{sources.length} {isEn ? "sources" : "nguồn"}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-500">{isEn ? "Linked citations:" : "Trích dẫn có nguồn:"}</span>
                    <span className="font-bold text-zinc-900">{citations.length} {isEn ? "claims" : "đoạn"}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-500">{isEn ? "Citation style:" : "Kiểu trích dẫn:"}</span>
                    <Badge variant="outline">{task.citation_style}</Badge>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-zinc-100">
                    <span className="text-zinc-500 text-xs">{isEn ? "Reading mode:" : "Chế độ đọc:"}</span>
                    <button
                      type="button"
                      onClick={handleToggleWidePaper}
                      className="text-blue-600 hover:text-blue-800 font-semibold cursor-pointer text-xs hover:underline flex items-center gap-1"
                    >
                      {isWidePaper ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                      <span>{isWidePaper ? (isEn ? "Standard width" : "Thu gọn về chuẩn") : (isEn ? "Full width" : "Phóng to toàn màn hình ↗")}</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Research Metadata */}
              <div className={`space-y-2 text-zinc-600 ${report ? 'pt-3 border-t border-zinc-200' : ''}`}>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500">{isEn ? "Research Type:" : "Loại nghiên cứu:"}</span>
                  <Badge variant="outline">
                    {task.research_type === 'EMPIRICAL_HUMAN' ? (isEn ? 'Fieldwork' : 'Thực địa') : task.research_type === 'EMPIRICAL_COMPUTATIONAL' ? (isEn ? 'Computational' : 'Tính toán') : (isEn ? 'Literature Review' : 'Tổng quan')}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500">{isEn ? "Tokens used:" : "Tokens tiêu thụ:"}</span>
                  <strong className="font-bold text-zinc-900 font-mono text-xs">{task.total_tokens_used.toLocaleString('vi-VN')}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500">{isEn ? "Estimated cost:" : "Chi phí ước tính:"}</span>
                  <strong className="font-bold text-zinc-900 font-mono text-xs">${Number(task.total_cost_usd).toFixed(4)}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500">{isEn ? "Updated:" : "Cập nhật:"}</span>
                  <span className="text-zinc-700 text-[11px]">{formatDate(task.updated_at, language)}</span>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Content Tabs Area */}

        {/* Content Tabs Area */}
        <main className="flex-1 flex flex-col bg-white overflow-hidden print:overflow-visible print:h-auto print:block">
          {task.status === 'WAITING_APPROVAL' && (
            <div id="plan-review-section" className="p-4 bg-amber-50/80 border-b border-amber-200 overflow-y-auto max-h-96 shrink-0 print:hidden">
              <div className="w-full max-w-7xl mx-auto space-y-3.5">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="p-1.5 rounded-lg bg-amber-200 text-amber-900 shrink-0">
                      <Clock size={18} />
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-sm text-amber-950">{isEn ? "Research Plan Approval (Human-in-the-Loop)" : "Phê duyệt kế hoạch nghiên cứu (Human-in-the-Loop)"}</h2>
                        <Badge variant="outline" className="border-amber-300 bg-amber-100 text-amber-900 text-[11px]">{isEn ? "Awaiting Approval" : "Đang chờ phê duyệt"}</Badge>
                      </div>
                      <p className="text-xs text-amber-800/90 mt-0.5">
                        {isEn ? "Supervisor Agent has drafted the scope and queries. Review the research angle and refine search keywords before agents gather data." : "Supervisor Agent đã hoàn thành đề cương. Bạn có thể kiểm tra góc nhìn, tinh chỉnh từ khóa tìm kiếm trước khi các Agent thu thập dữ liệu."}
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
                      {isEn ? "Request Revision" : "Yêu cầu lập lại"}
                    </Button>
                    <Button
                      variant="primary"
                      onClick={() => void handleApprovePlan()}
                      isLoading={isApprovingPlan}
                      className="h-8 px-3 text-xs bg-amber-900 hover:bg-amber-950 text-white"
                    >
                      <Check size={14} className="mr-1.5" /> {isEn ? "Approve Plan & Proceed" : "Duyệt kế hoạch & Chạy tiếp"}
                    </Button>
                  </div>
                </div>

                {task.plan && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    {task.plan.research_angle && (
                      <div className="p-3 bg-white rounded-xl border border-amber-200/80 shadow-2xs">
                        <span className="font-medium text-amber-950 block mb-1">{isEn ? "Research Angle & Scope:" : "Góc nhìn & Hướng tiếp cận:"}</span>
                        <p className="text-zinc-700 leading-relaxed">{task.plan.research_angle}</p>
                      </div>
                    )}
                    {task.plan.required_sections && Array.isArray(task.plan.required_sections) && (
                      <div className="p-3 bg-white rounded-xl border border-amber-200/80 shadow-2xs">
                        <span className="font-medium text-amber-950 block mb-1.5">{isEn ? "Planned Outline & Sections:" : "Cấu trúc báo cáo dự kiến:"}</span>
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
                    <span className="font-medium text-amber-950">{isEn ? "Web Search Queries" : "Các truy vấn tìm kiếm Web"} ({editableQueries.length}):</span>
                    <span className="text-[11px] text-zinc-400">{isEn ? "Click × to remove, or enter a new query below" : "Nhấn dấu × để xóa, hoặc thêm từ khóa mới"}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {editableQueries.map((query, idx) => (
                      <span key={idx} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-100 text-zinc-800 border border-zinc-200 text-xs">
                        <span>{query}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveQuery(idx)}
                          className="text-zinc-400 hover:text-red-600 font-bold ml-1 text-xs"
                          title={isEn ? "Remove query" : "Xóa truy vấn"}
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
                      placeholder={isEn ? "Add new search keyword or query..." : "Thêm từ khóa tìm kiếm mới..."}
                      className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-900"
                    />
                    <Button variant="outline" className="h-8 px-3 text-xs" onClick={handleAddQuery}>
                      {isEn ? "Add" : "Thêm"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {task.status === 'WAITING_USER_DATA' && task.research_type === 'EMPIRICAL_COMPUTATIONAL' && (
            <div id="fieldwork-section" className="p-4 bg-indigo-50 border-b border-indigo-200 text-sm print:hidden" role="status">
              {isEn ? "Computational run is awaiting a CSV dataset. Upload data under Experiments & Journal to proceed." : "Bài tính toán đang chờ tập dữ liệu CSV. Tải dữ liệu trong mục Thực nghiệm để tiếp tục."}
              <Button variant="outline" className="ml-3" onClick={() => setActiveTab('experiments')}>{isEn ? "Open Experiments" : "Mở thực nghiệm"}</Button>
            </div>
          )}

          {task.status === 'WAITING_USER_DATA' && task.research_type === 'EMPIRICAL_HUMAN' && (
            <div id="fieldwork-section" className="p-6 sm:p-8 bg-indigo-50/90 border-b-2 border-indigo-200 overflow-y-auto max-h-[44rem] shrink-0 print:hidden shadow-xs">
              <div className="w-full max-w-7xl mx-auto space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="p-1.5 rounded-lg bg-indigo-200 text-indigo-900 shrink-0">
                      <FlaskConical size={18} />
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-sm text-indigo-950">{isEn ? "Study Protocol Ready & Awaiting Fieldwork Data" : "Đề cương nghiên cứu sẵn sàng & Chờ dữ liệu thực nghiệm"}</h2>
                        <Badge variant="outline" className="border-indigo-300 bg-indigo-100 text-indigo-900 text-[11px]">{isEn ? "Awaiting User Data" : "Chờ dữ liệu người dùng"}</Badge>
                      </div>
                      <p className="text-xs text-indigo-800/90 mt-0.5">
                        {isEn ? <>Methodologist Agent has prepared the research protocol. Download <code className="bg-indigo-100 px-1 rounded font-mono">study_protocol.md</code>, conduct surveys or empirical collection, then submit summarized data below to proceed.</> : <>Agent Methodologist đã hoàn thành đề cương phương pháp. Hãy tải file <code className="bg-indigo-100 px-1 rounded font-mono">study_protocol.md</code>, tiến hành khảo sát hoặc đo đạc, sau đó cung cấp dữ liệu tóm tắt bên dưới để tiếp tục viết báo cáo.</>}
                      </p>
                    </div>
                  </div>
                  {task.protocol_artifact_id && (
                    <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                      <Button
                        variant="outline"
                        onClick={() => void handleDownloadArtifact(task.protocol_artifact_id!, 'study_protocol.md')}
                        className="h-10 px-4 text-xs sm:text-sm font-semibold border-indigo-300 text-indigo-950 hover:bg-indigo-100/80 rounded-xl"
                      >
                        <Download size={13} className="mr-1.5" /> {isEn ? "Download Protocol (.md)" : "Tải đề cương (.md)"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setActiveTab('protocol')}
                        className="h-10 px-4 text-xs sm:text-sm font-semibold border-indigo-300 text-indigo-950 hover:bg-indigo-100/80 rounded-xl"
                      >
                        <FileText size={13} className="mr-1.5" /> {isEn ? "View Full Protocol" : "Xem đề cương chi tiết"}
                      </Button>
                    </div>
                  )}
                </div>

                {protocol?.content_markdown && (
                  <div className="p-3 bg-white rounded-xl border border-indigo-200/80 text-xs">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-indigo-950">{isEn ? "Protocol Excerpt:" : "Trích đoạn đề cương nghiên cứu:"}</span>
                      <button
                        type="button"
                        onClick={() => setActiveTab('protocol')}
                        className="text-indigo-600 hover:underline font-medium text-[11px]"
                      >
                        {isEn ? "View full protocol →" : "Xem toàn bộ đề cương →"}
                      </button>
                    </div>
                    <div className="max-h-36 overflow-y-auto p-2.5 bg-zinc-50 rounded-lg text-zinc-700 font-mono text-[11px] whitespace-pre-wrap leading-relaxed">
                      {protocol.content_markdown.slice(0, 500)}...
                    </div>
                  </div>
                )}

                <form onSubmit={handleResumeWithData} className="p-6 bg-white rounded-2xl border border-indigo-200 text-sm space-y-4 shadow-sm">
                  <div className="flex items-center justify-between border-b border-zinc-100 pb-2">
                    <span className="font-extrabold text-indigo-950 text-base sm:text-lg">{isEn ? "Submit Fieldwork / Empirical Data" : "Cung cấp dữ liệu thực địa / thực nghiệm"}</span>
                    <span className="text-[11px] text-zinc-400">{isEn ? "* Result file and provenance are required" : "* Tệp kết quả và nguồn gốc là bắt buộc"}</span>
                  </div>

                  <div className="space-y-3 p-3.5 bg-zinc-50 rounded-xl border border-zinc-200">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div>
                        <label htmlFor="fieldwork-file" className="block font-semibold text-zinc-900 text-xs">
                          {isEn ? "Upload Fieldwork Result File (CSV / TXT UTF-8, max 5 MiB)" : "Tải tệp kết quả thực địa (CSV / TXT UTF-8, tối đa 5 MiB)"} <span className="text-red-500">*</span>
                        </label>
                        <p className="text-[11px] text-zinc-500 mt-0.5">
                          {isEn ? "Tabular dataset (.csv) or measurement log report (.txt) with all personal identifiers removed." : "Tệp bảng số liệu (.csv) hoặc báo cáo nhật ký đo lường (.txt) đã loại bỏ danh tính."}
                        </p>
                      </div>
                      <div>
                        <input
                          id="fieldwork-file"
                          type="file"
                          accept=".csv,.txt"
                          onChange={handleUploadResult}
                          disabled={isUploadingResult || isResumingData}
                          className="hidden"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => document.getElementById('fieldwork-file')?.click()}
                          disabled={isUploadingResult || isResumingData}
                          className="text-sm h-11 px-5 font-bold rounded-xl border-zinc-300 hover:bg-zinc-100"
                        >
                          <UploadCloud size={13} className="mr-1.5" />
                          {isUploadingResult ? (isEn ? 'Uploading...' : 'Đang nạp...') : (isEn ? 'Upload Result File' : 'Tải tệp kết quả')}
                        </Button>
                      </div>
                    </div>

                    {isUploadingResult && (
                      <div className="flex items-center gap-2 text-indigo-700 bg-indigo-50 p-2 rounded-lg text-xs" role="status">
                        <div className="w-3.5 h-3.5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                        <span>{isEn ? "Uploading and verifying SHA-256 checksum..." : "Đang tải và kiểm tra chữ ký SHA-256 của tệp..."}</span>
                      </div>
                    )}

                    <div>
                      <label htmlFor="fieldwork-artifact" className="block text-[11px] font-medium text-zinc-700 mb-1">
                        {isEn ? "Selected result file for this run:" : "Tệp kết quả chọn dùng cho lần tiếp tục này:"} <span className="text-red-500">*</span>
                      </label>
                      <select
                        id="fieldwork-artifact"
                        required
                        value={resultArtifactId}
                        onChange={e => setResultArtifactId(e.target.value)}
                        disabled={isUploadingResult || isResumingData}
                        className="w-full rounded-lg border border-zinc-300 p-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-indigo-900"
                      >
                        <option value="">{isEn ? "-- Select uploaded result file --" : "-- Chọn tệp kết quả đã tải lên --"}</option>
                        {artifacts.filter(a => ['USER_DATA_CSV', 'USER_DATA_TEXT'].includes(a.export_type)).map(a => (
                          <option key={a.id} value={a.id}>{a.file_path.split('/').pop()} ({(a.file_size_bytes / 1024).toFixed(1)} KB)</option>
                        ))}
                      </select>
                    </div>

                    <p className="text-[11px] text-zinc-500 italic">
                      {isEn ? "Note: Data is user-provided and not independently verified by the system. State provenance, collection date, and responsible party clearly; anonymize all personal data." : "Lưu ý: Kết quả do bạn cung cấp, chưa được hệ thống xác minh độc lập. Ghi rõ cách thu thập, thời điểm và người chịu trách nhiệm; chỉ nạp dữ liệu đã loại bỏ thông tin định danh cá nhân."}
                    </p>
                    {resultFileError && <p role="alert" className="text-xs text-red-700 bg-red-50 p-2 rounded-lg border border-red-200">{resultFileError}</p>}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-medium text-zinc-600 mb-1">
                        {isEn ? "Actual Sample Size Collected" : "Cỡ mẫu thực tế thu thập được"} <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        min="1"
                        required
                        value={sampleSize}
                        onChange={e => setSampleSize(e.target.value)}
                        placeholder={isEn ? "e.g. 150" : "VD: 150"}
                        className="w-full px-3 py-1.5 text-xs rounded-lg border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-900"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-zinc-600 mb-1">{isEn ? "Data Provenance / Source *" : "Nguồn gốc / Xuất xứ dữ liệu *"}</label>
                      <input
                        type="text"
                        value={dataProvenance}
                        required
                        minLength={10}
                        maxLength={2000}
                        onChange={e => setDataProvenance(e.target.value)}
                        placeholder={isEn ? "e.g. Field survey of engineering students, Oct 2026" : "VD: Khảo sát thực địa sinh viên Đại học Bách Khoa, 10/2026"}
                        className="w-full px-3 py-1.5 text-xs rounded-lg border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-900"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-zinc-600 mb-1">
                      {isEn ? "Data Collection Methodology & Procedure" : "Phương pháp & quy trình thu thập"} <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      minLength={10}
                      value={methodNotes}
                      maxLength={5000}
                      onChange={e => setMethodNotes(e.target.value)}
                      placeholder={isEn ? "e.g. Online Google Forms survey, 5-point Likert scale, processed with Python" : "VD: Bảng hỏi trực tuyến Google Forms, thang đo Likert 5 mức, xử lý dữ liệu với SPSS/Python"}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-900"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-zinc-600 mb-1">
                      {isEn ? "Empirical Findings & Data Summary" : "Tóm tắt kết quả thực nghiệm / dữ liệu thu thập"} <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      rows={3}
                      required
                      value={resultsSummary}
                      minLength={10}
                      maxLength={20000}
                      onChange={e => setResultsSummary(e.target.value)}
                      placeholder={isEn ? "Summarize empirical metrics, calculations, and empirical limits. Do not enter unverified conclusions or uncalculated p-values." : "Tóm tắt số liệu thực tế trong tệp, cách tính và các giới hạn. Không điền kết luận hoặc p-value chưa được phân tích."}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-900 leading-relaxed"
                    />
                  </div>

                  <div className="flex justify-end pt-1">
                    <Button
                      type="submit"
                      variant="primary"
                      isLoading={isResumingData}
                      disabled={isUploadingResult || !resultArtifactId}
                      className="h-8 px-4 text-xs bg-indigo-900 hover:bg-indigo-950 text-white"
                    >
                      <Check size={14} className="mr-1.5" /> {isEn ? "Submit Data & Resume Research" : "Gửi dữ liệu & Tiếp tục nghiên cứu"}
                    </Button>
                  </div>
                </form>
              </div>
            </div>
          )}

                    <div id="research-tab-bar" className="flex border-b-2 border-zinc-200 px-4 sm:px-6 bg-zinc-50 shrink-0 gap-2 overflow-x-auto no-scrollbar print:hidden">
            <button
              onClick={() => setActiveTab('report')}
              className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                activeTab === 'report'
                  ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
              }`}
            >
              <FileText size={18} className={activeTab === 'report' ? 'text-zinc-950' : 'text-zinc-500'} />
              <span>{isEn ? 'Scientific Paper' : 'Bài báo'}</span>
              {report && (
                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                  activeTab === 'report' ? 'bg-zinc-900 text-white' : 'bg-zinc-200 text-zinc-800'
                }`}>
                  {report.word_count.toLocaleString()} {isEn ? 'words' : 'từ'}
                </span>
              )}
            </button>

            {(task.protocol_artifact_id || protocol) && (
              <button
                onClick={() => setActiveTab('protocol')}
                className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                  activeTab === 'protocol'
                    ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                    : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
                }`}
              >
                <FlaskConical size={18} className={activeTab === 'protocol' ? 'text-zinc-950' : 'text-zinc-500'} />
                <span>{isEn ? 'Study Protocol' : 'Đề cương nghiên cứu'}</span>
              </button>
            )}

            {task.research_type === 'EMPIRICAL_COMPUTATIONAL' && (
              <button
                onClick={() => setActiveTab('experiments')}
                className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                  activeTab === 'experiments'
                    ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                    : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
                }`}
              >
                <Cpu size={18} className={activeTab === 'experiments' ? 'text-zinc-950' : 'text-zinc-500'} />
                <span>{isEn ? 'Experiments & Journal' : 'Thực nghiệm & Nhật ký'}</span>
                {experiments.length > 0 && (
                  <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                    activeTab === 'experiments' ? 'bg-zinc-900 text-white' : 'bg-zinc-200 text-zinc-800'
                  }`}>
                    {experiments.length}
                  </span>
                )}
              </button>
            )}

            <button
              onClick={() => setActiveTab('sources')}
              className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                activeTab === 'sources'
                  ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
              }`}
            >
              <Globe size={18} className={activeTab === 'sources' ? 'text-zinc-950' : 'text-zinc-500'} />
              <span>{isEn ? 'Sources' : 'Nguồn tài liệu'}</span>
              {sources.length > 0 && (
                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                  activeTab === 'sources' ? 'bg-zinc-900 text-white' : 'bg-zinc-200 text-zinc-800'
                }`}>
                  {sources.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('citations')}
              className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                activeTab === 'citations'
                  ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
              }`}
            >
              <Layers size={18} className={activeTab === 'citations' ? 'text-zinc-950' : 'text-zinc-500'} />
              <span>{isEn ? 'Evidence & Citations' : 'Bằng chứng & Trích dẫn'}</span>
              {citations.length > 0 && (
                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                  activeTab === 'citations' ? 'bg-zinc-900 text-white' : 'bg-zinc-200 text-zinc-800'
                }`}>
                  {citations.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('runs')}
              className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                activeTab === 'runs'
                  ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
              }`}
            >
              <Activity size={18} className={activeTab === 'runs' ? 'text-zinc-950' : 'text-zinc-500'} />
              <span>{isEn ? 'Agent Runs & Cost' : 'Tiến trình Agent & Chi phí'}</span>
              {runs.length > 0 && (
                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                  activeTab === 'runs' ? 'bg-zinc-900 text-white' : 'bg-zinc-200 text-zinc-800'
                }`}>
                  {runs.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('details')}
              className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                activeTab === 'details'
                  ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100/70 font-bold'
              }`}
            >
              <Info size={18} className={activeTab === 'details' ? 'text-zinc-950' : 'text-zinc-500'} />
              <span>{isEn ? 'Metadata & Config' : 'Thông tin & Cấu hình'}</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 bg-zinc-50/60 print:overflow-visible print:h-auto print:p-0 print:m-0 print:bg-white print:block">
            {/* TAB 1: SCIENTIFIC PAPER */}
            {task.status === 'FAILED' && <ResearchErrorNotice isEn={isEn}
              error={runs.find(run => run.status === 'FAILED' && run.attempt_number === task.attempt_number)?.error_message} />}
            {activeTab === 'report' && (
              <div className={`paper-space w-full ${isWidePaper ? 'max-w-6xl' : 'max-w-4xl'} mx-auto space-y-6 transition-all duration-300 print:max-w-none print:m-0 print:p-0 print:space-y-0`}>
                {(['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(task.status) || report?.research_task_id === params.id) ? report?.research_task_id === params.id ? (
                  <div className="space-y-6 print:space-y-0">
                    <ManuscriptReadiness report={report} taskId={params.id} isEn={isEn} />
                    {['FAILED', 'CANCELLED'].includes(task.status) && (
                      <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800 flex items-center justify-between print:hidden">
                        <span>{statusLabel(task.status, language)} — {['FAILED', 'CANCELLED'].includes(task.status)
                          ? (isEn ? `Showing saved version ${report.version_number}; the latest operation did not replace it.` : `Đang hiển thị phiên bản ${report.version_number} đã lưu; thao tác vừa rồi không ghi đè bản này.`)
                          : (isEn ? 'Review evidence, validation findings and remaining limitations before use.' : 'Cần rà soát bằng chứng, kết quả kiểm tra và các hạn chế trước khi sử dụng.')}</span>
                        <Badge variant="outline">{statusLabel(task.status, language)}</Badge>
                      </div>
                    )}

                    {/* Scientific Journal 2-Column Presentation */}
                    <div className="paper-layout-container printable-paper-container">
                      {/* Main Scientific Paper Document */}
                      <article className="printable-article w-full min-w-0 bg-white rounded-2xl border border-zinc-200/90 shadow-sm overflow-hidden print:border-none print:shadow-none print:p-0 print:m-0 print:rounded-none">
                        {/* Journal Cover / Top Masthead */}
                        <div className="border-b border-zinc-200 bg-gradient-to-b from-zinc-50/80 to-white px-6 sm:px-10 md:px-12 pt-8 pb-7 print:px-0 print:pt-0 print:bg-none print:border-b-2 print:border-zinc-800">
                          {/* Academic Meta Topline */}
                          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-500 font-mono border-b border-zinc-100 pb-3 mb-5 print:border-zinc-300">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded bg-zinc-900 text-white font-bold tracking-wider text-[10px] uppercase font-sans print:border print:border-zinc-800">
                                Synthia Research Draft
                              </span>
                              <span className="text-zinc-300">|</span>
                              <span className="font-semibold text-zinc-700 tracking-wide">
                                {task.research_type === 'EMPIRICAL_COMPUTATIONAL'
                                  ? 'COMPUTATIONAL INVESTIGATION REPORT'
                                  : task.research_type === 'EMPIRICAL_HUMAN'
                                  ? 'EMPIRICAL FIELD STUDY & PROTOCOL'
                                  : 'LITERATURE REVIEW & SYNTHESIS'}
                              </span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span>{isEn ? 'Draft version' : 'Phiên bản bản thảo'} {report.version_number}</span>
                              <span>•</span>
                              <span>{formatDate(report.created_at, language)}</span>
                            </div>
                          </div>

                          {/* Paper Title */}
                          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-zinc-900 tracking-tight leading-tight">
                            {report.title}
                          </h1>

                          {/* Authors & Laboratory Metadata */}
                          <div className="mt-5 pt-4 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-4 text-xs print:border-zinc-300">
                            <div>
                              <div className="font-semibold text-zinc-800 text-sm">
                                {isEn ? 'AI-assisted research draft' : 'Bản thảo nghiên cứu có AI hỗ trợ'}
                              </div>
                              <div className="text-zinc-500 mt-0.5">
                                {isEn ? 'Verify claims and references before academic use.' : 'Cần kiểm chứng luận điểm và nguồn trước khi sử dụng học thuật.'}
                              </div>
                              <div className="text-zinc-400 mt-0.5 text-[11px] print:hidden">
                                {isEn ? 'Not a published or peer-reviewed article.' : 'Chưa phải bài báo đã xuất bản hoặc qua phản biện học thuật.'}
                              </div>
                            </div>

                            {/* Quick Actions */}
                            <div className="flex flex-wrap items-center gap-2 print:hidden">
                              <Button
                                variant="outline"
                                onClick={() => window.print()}
                                title={isEn ? "Print full paper or Save as PDF" : "In toàn bộ bài báo hoặc Lưu thành PDF"}
                                className="h-8 px-2.5 text-xs hover:bg-zinc-100 cursor-pointer"
                              >
                                <Printer size={13} className="mr-1.5" /> {isEn ? 'Print / PDF' : 'In / PDF'}
                              </Button>
                              <Button
                                variant="outline"
                                onClick={handleCopyMarkdown}
                                title={isEn ? "Copy full Markdown content" : "Sao chép toàn bộ nội dung Markdown"}
                                className="h-8 px-2.5 text-xs hover:bg-zinc-100 cursor-pointer"
                              >
                                {isCopied ? <Check size={13} className="text-emerald-600 mr-1.5" /> : <Copy size={13} className="mr-1.5" />}
                                {isCopied ? (isEn ? "Copied" : "Đã chép") : (isEn ? "Copy" : "Sao chép")}
                              </Button>
                              <Button
                                variant={isWidePaper ? "primary" : "outline"}
                                onClick={handleToggleWidePaper}
                                title={isWidePaper ? (isEn ? "Exit full width reading (show sidebars)" : "Thu gọn về kích thước chuẩn (hiện thanh bên)") : (isEn ? "Full width reading mode (hide sidebars)" : "Phóng to toàn màn hình (ẩn thanh bên)")}
                                className={`h-8 px-2.5 text-xs font-semibold cursor-pointer ${isWidePaper ? 'bg-zinc-900 text-white' : 'hover:bg-zinc-100'}`}
                              >
                                {isWidePaper ? <Minimize2 size={13} className="mr-1.5" /> : <Maximize2 size={13} className="mr-1.5" />}
                                {isWidePaper ? (isEn ? "Standard" : "Thu gọn") : (isEn ? "Full Width" : "Phóng to")}
                              </Button>

                              {/* Download Formats Dropdown */}
                              <div className="relative">
                                <Button
                                  variant="primary"
                                  onClick={() => setIsDownloadMenuOpen(prev => !prev)}
                                  disabled={isExportingDocx}
                                  title={isEn ? "Select download format (Word, Markdown, JSON)" : "Chọn định dạng tải bài báo (Word, Markdown, JSON)"}
                                  className="h-8 px-3 text-xs bg-zinc-900 hover:bg-zinc-800 text-white cursor-pointer shadow-xs flex items-center"
                                >
                                  {isExportingDocx ? (
                                    <Loader2 size={13} className="mr-1.5 animate-spin" />
                                  ) : (
                                    <Download size={13} className="mr-1.5" />
                                  )}
                                  <span>{isExportingDocx ? (isEn ? "Exporting Word..." : "Đang tạo Word...") : (isEn ? "Download" : "Tải về")}</span>
                                  <ChevronDown size={13} className={`ml-1.5 transition-transform duration-150 ${isDownloadMenuOpen ? 'rotate-180' : ''}`} />
                                </Button>

                                {isDownloadMenuOpen && (
                                  <>
                                    <div
                                      className="fixed inset-0 z-40"
                                      onClick={() => setIsDownloadMenuOpen(false)}
                                    />
                                    <div className="absolute right-0 mt-1.5 w-72 rounded-xl bg-white border border-zinc-200 shadow-xl py-1.5 z-50 text-left">
                                      <div className="px-3 py-1.5 text-[10.5px] font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-100">
                                        {isEn ? "Select download format" : "Chọn định dạng tải xuống"}
                                      </div>

                                      {/* Word (.docx) */}
                                      <button
                                        type="button"
                                        onClick={async () => {
                                          setIsDownloadMenuOpen(false);
                                          await handleDownloadDocx();
                                        }}
                                        className="w-full px-3 py-2.5 text-left hover:bg-zinc-100 flex items-start gap-3 transition-colors cursor-pointer group"
                                      >
                                        <div className="p-1.5 rounded-lg bg-zinc-100 text-zinc-700 group-hover:bg-zinc-200 shrink-0 mt-0.5">
                                          <FileDown size={16} />
                                        </div>
                                        <div>
                                          <div className="font-semibold text-xs text-zinc-900 group-hover:text-blue-900 flex items-center gap-1.5">
                                            Microsoft Word (.docx)
                                            <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 font-medium border border-zinc-200">{isEn ? "Recommended" : "Khuyên dùng"}</span>
                                          </div>
                                          <div className="text-[11px] text-zinc-500 mt-0.5 leading-snug">
                                            {isEn ? "Standard formatted Word document with tables, outline, and references" : "Văn bản Word chuẩn báo cáo khoa học với bảng, danh mục và tài liệu tham khảo"}
                                          </div>
                                        </div>
                                      </button>

                                      {/* Markdown (.md) */}
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setIsDownloadMenuOpen(false);
                                          handleDownloadMarkdown();
                                        }}
                                        className="w-full px-3 py-2.5 text-left hover:bg-zinc-100 flex items-start gap-3 transition-colors cursor-pointer group"
                                      >
                                        <div className="p-1.5 rounded-lg bg-zinc-100 text-zinc-700 group-hover:bg-zinc-200 shrink-0 mt-0.5">
                                          <FileText size={16} />
                                        </div>
                                        <div>
                                          <div className="font-semibold text-xs text-zinc-900 group-hover:text-emerald-900">
                                            Markdown (.md)
                                          </div>
                                          <div className="text-[11px] text-zinc-500 mt-0.5 leading-snug">
                                            {isEn ? "Standard Markdown text source file" : "Tệp văn bản nguồn định dạng Markdown tiêu chuẩn"}
                                          </div>
                                        </div>
                                      </button>

                                      <div className="border-t border-zinc-100 my-1"></div>

                                      {/* JSON Data Bundle */}
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setIsDownloadMenuOpen(false);
                                          handleDownloadBundle();
                                        }}
                                        className="w-full px-3 py-2.5 text-left hover:bg-zinc-100 flex items-start gap-3 transition-colors cursor-pointer group"
                                      >
                                        <div className="p-1.5 rounded-lg bg-zinc-100 text-zinc-700 group-hover:bg-zinc-200 shrink-0 mt-0.5">
                                          <Package size={16} />
                                        </div>
                                        <div>
                                          <div className="font-semibold text-xs text-zinc-900 group-hover:text-amber-900">
                                            {isEn ? "Research data bundle (.json)" : "Gói dữ liệu nghiên cứu (.json)"}
                                          </div>
                                          <div className="text-[11px] text-zinc-500 mt-0.5 leading-snug">
                                            {isEn ? "Includes full paper, retrieved sources, and verified citations" : "Bao gồm bài báo, nguồn tài liệu và trích dẫn bằng chứng"}
                                          </div>
                                        </div>
                                      </button>
                                    </div>
                                  </>
                                )}
                              </div>


                            </div>
                          </div>


                        </div>

                        <PublicationExport taskId={task.id} version={report.version_number} isEn={isEn} />
                        {/* Scientific Article Body rendered by MarkdownViewer with academicStyle */}
                        <div className="px-6 sm:px-10 md:px-12 py-8">
                          <PublicationArticle metadata={report.review_metadata}
                            content={withoutRepeatedTitle(report.content_markdown, report.title)}
                            academicStyle={true}
                            onCitationClick={(label) => {
                              setHighlightedRef(label);
                              setActiveTab('citations');
                            }}
                          />
                        </div>

                        {/* Publication Footer */}
                        <div className="border-t border-zinc-200 bg-zinc-50/70 px-6 sm:px-10 py-5 text-xs text-zinc-500 flex flex-wrap items-center justify-between gap-4 print:bg-white print:px-0">
                          <div>
                            <div className="font-medium text-zinc-700">Synthia Multi-Agent Research Platform</div>
                            <div>{isEn ? "AI-assisted draft linked to source passages; claims still require scientific review." : "Bản thảo có AI hỗ trợ, gắn với trích đoạn nguồn; luận điểm vẫn cần kiểm chứng khoa học."}</div>
                          </div>
                          <div className="font-mono text-[11px] text-zinc-400">
                            ID: {task.id} · v{report.version_number}
                          </div>
                        </div>
                      </article>

                      {/* Right Sidebar: Table of Contents & Article Metadata */}
                                            
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-zinc-600">
                    {reportError || (isEn ? 'Preparing scientific paper draft...' : 'Đang chuẩn bị bản thảo bài báo...')}
                    {reportError && <button className="underline ml-2" onClick={() => void loadReport()}>{isEn ? "Retry" : "Thử lại"}</button>}
                  </div>
                ) : (
                  <div className="w-full max-w-5xl mx-auto space-y-6">
                    {/* Live Execution Status Hero */}
                    <div className={`p-6 sm:p-8 rounded-2xl border transition-all ${
                      task.status === 'QUEUED'
                        ? 'bg-gradient-to-b from-zinc-50 to-white border-zinc-300 shadow-sm'
                        : task.status === 'PLANNING'
                        ? 'bg-gradient-to-b from-blue-50/70 to-white border-blue-200 shadow-sm'
                        : isWorking
                        ? 'bg-gradient-to-b from-blue-50/60 to-white border-blue-200 shadow-sm'
                        : task.status === 'FAILED'
                        ? 'bg-gradient-to-b from-red-50/60 to-white border-red-200'
                        : 'bg-white border-zinc-200 shadow-sm'
                    }`}>
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {task.status === 'QUEUED' ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-200/80 text-zinc-800 text-xs font-bold uppercase tracking-wider">
                                <span className="w-2 h-2 rounded-full bg-zinc-500 animate-pulse" />
                                {isEn ? "Task Queued" : "Đang chờ xếp hàng"}
                              </span>
                            ) : task.status === 'PLANNING' ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-900 text-xs font-bold uppercase tracking-wider">
                                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                                {isEn ? "Planning Phase" : "Giai đoạn lập kế hoạch"}
                              </span>
                            ) : isWorking ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-900 text-xs font-bold uppercase tracking-wider">
                                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                                {statusLabel(task.status, language)}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-100 text-zinc-800 text-xs font-bold uppercase tracking-wider">
                                {statusLabel(task.status, language)}
                              </span>
                            )}

                            {task.current_step && isWorking && (
                              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200">
                                {stepLabel(task.current_step, language)}
                              </span>
                            )}
                          </div>

                          <h2 className="text-xl sm:text-2xl font-bold text-zinc-900 tracking-tight">
                            {task.status === 'QUEUED'
                              ? (isEn ? "Research task is queued for agent worker allocation" : "Bài nghiên cứu đang trong hàng đợi chờ phân phối tác tử")
                              : task.status === 'PLANNING'
                              ? (isEn ? "Supervisor Agent is planning research strategy & queries" : "Supervisor Agent đang phân tích đề tài & thiết lập từ khóa")
                              : isWorking
                              ? (isEn ? "Autonomous agents are gathering and synthesizing evidence" : "Các tác tử tự trị đang thu thập và phân tích dữ liệu")
                              : task.status === 'FAILED'
                              ? (isEn ? "Research stopped due to an execution error" : "Bài nghiên cứu đã dừng do phát sinh lỗi")
                              : task.status === 'CANCELLED'
                              ? (isEn ? "Research task was cancelled" : "Bài nghiên cứu đã được hủy")
                              : (isEn ? "Research task is ready to begin" : "Bài nghiên cứu sẵn sàng bắt đầu")}
                          </h2>

                          <p className="text-sm text-zinc-600 leading-relaxed max-w-2xl">
                            {task.status === 'QUEUED'
                              ? (isEn
                                  ? "Your research question has been registered. An autonomous agent worker is being scheduled to initiate literature discovery. Polling updates automatically."
                                  : "Đề tài nghiên cứu đã được ghi nhận vào hệ thống. Máy chủ đang xếp lịch tác tử để bắt đầu tìm kiếm tài liệu. Giao diện tự động cập nhật.")
                              : task.status === 'PLANNING'
                              ? (isEn
                                  ? "The Supervisor Agent is deconstructing your topic into core domain hypotheses, identifying academic databases, and generating targeted search queries."
                                  : "Supervisor Agent đang phân rã câu hỏi nghiên cứu thành các luận điểm học thuật, xác định cơ sở dữ liệu và soạn thảo truy vấn tìm kiếm chuyên sâu.")
                              : isWorking
                              ? (isEn
                                  ? "Literature is being fetched, chunked, and embedded into the vector database. Analysts will cross-reference claims before drafting the final paper."
                                  : "Tài liệu đang được thu thập, trích xuất đoạn và nhúng vào vector database. Agent phân tích sẽ đối soát chéo bằng chứng trước khi soạn thảo.")
                              : task.status === 'FAILED'
                              ? (isEn
                                  ? "An error occurred during workflow execution. Check the Agent Runs tab or Live Monitor for diagnostic logs."
                                  : "Đã xảy ra sự cố trong quá trình thực thi. Vui lòng kiểm tra tab Tiến trình Agent hoặc Màn hình giám sát để xem log.")
                              : task.status === 'CANCELLED'
                              ? (isEn
                                  ? "Execution was manually cancelled. You can restart the pipeline at any time with the button below."
                                  : "Tiến trình đã được dừng theo lệnh người dùng. Bạn có thể bấm khởi động lại bất cứ lúc nào.")
                              : (isEn
                                  ? "Click 'Start Research Now' to deploy the multi-agent pipeline."
                                  : "Nhấn 'Bắt đầu nghiên cứu ngay' để khởi chạy chuỗi tác tử.")}
                          </p>
                        </div>

                        {/* Real-time stats / action buttons */}
                        <div className="flex flex-col sm:flex-row md:flex-col gap-2.5 shrink-0 self-start md:self-center">
                          {(task.status === 'PENDING' || task.status === 'CANCELLED') && (
                            <Button
                              variant="primary"
                              onClick={() => void handleStartTask()}
                              isLoading={isStarting}
                              className="h-10 px-5 text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 text-white shadow-sm"
                            >
                              <Play size={16} className="mr-2" />
                              {task.status === 'CANCELLED' ? (isEn ? 'Rerun Research' : 'Chạy lại nghiên cứu') : (isEn ? 'Start Research Now' : 'Bắt đầu nghiên cứu ngay')}
                            </Button>
                          )}

                          <Link
                            href={`/research/${task.id}/monitor`}
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 text-xs sm:text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm"
                          >
                            <Activity size={16} />
                            <span>{isEn ? "Open Live Monitor" : "Mở màn hình giám sát trực tiếp"}</span>
                          </Link>

                          <Button
                            variant="outline"
                            onClick={() => setReloadKey(v => v + 1)}
                            className="h-9 px-3 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-100"
                          >
                            <RefreshCw size={13} className="mr-1.5" />
                            <span>{isEn ? "Refresh Status" : "Làm mới trạng thái"}</span>
                          </Button>
                        </div>
                      </div>

                      {/* Live counters if active */}
                      {(isWorking || sources.length > 0 || runs.length > 0) && (
                        <div className="mt-5 pt-4 border-t border-zinc-200/80 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                          <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
                            <span className="text-zinc-500 font-medium block">{isEn ? "Sources Found" : "Nguồn thu thập"}</span>
                            <span className="text-lg font-bold text-zinc-900">{sources.length}</span>
                          </div>
                          <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
                            <span className="text-zinc-500 font-medium block">{isEn ? "Source-linked Claims" : "Luận điểm có nguồn"}</span>
                            <span className="text-lg font-bold text-zinc-900">{citations.length}</span>
                          </div>
                          <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
                            <span className="text-zinc-500 font-medium block">{isEn ? "Tokens Consumed" : "Tokens tiêu thụ"}</span>
                            <span className="text-lg font-bold text-zinc-900 font-mono">{task.total_tokens_used.toLocaleString()}</span>
                          </div>
                          <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
                            <span className="text-zinc-500 font-medium block">{isEn ? "Estimated Cost" : "Chi phí ước tính"}</span>
                            <span className="text-lg font-bold text-emerald-700 font-mono">${Number(task.total_cost_usd).toFixed(4)}</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Deliverables Section - Clarifying what this pipeline delivers */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-bold text-base sm:text-lg text-zinc-900">
                            {isEn ? "Expected Research Deliverables" : "Các sản phẩm hệ thống sẽ bàn giao"}
                          </h3>
                          <p className="text-xs text-zinc-600 mt-0.5">
                            {isEn
                              ? "A run may produce a draft and supporting records for the selected study type. Outputs can be incomplete and require human review."
                              : "Sau một lượt chạy, hệ thống có thể tạo bản thảo và hồ sơ hỗ trợ phù hợp với loại nghiên cứu đã chọn. Kết quả có thể chưa hoàn chỉnh và cần con người rà soát."}
                          </p>
                        </div>
                        <span className="text-xs font-medium px-2.5 py-1 rounded-md bg-zinc-100 text-zinc-700 border border-zinc-200 hidden sm:inline-block">
                          {task.citation_style} • {task.research_type}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {/* Deliverable 1: Academic Paper */}
                        <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                          <div className="flex items-center gap-2.5">
                            <div className="p-2 rounded-lg bg-blue-50 text-blue-700 border border-blue-100 shrink-0">
                              <FileText size={18} />
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-zinc-900">
                                {isEn ? "1. AI-Assisted Research Draft" : "1. Bản thảo nghiên cứu có AI hỗ trợ"}
                              </h4>
                              <span className="text-[11px] text-zinc-600 font-medium">{isEn ? "Structured for the selected study type" : "Bố cục theo loại nghiên cứu đã chọn"}</span>
                            </div>
                          </div>
                          <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                            {isEn
                              ? "The draft may contain sections relevant to the selected method. It is not peer-reviewed or publication-ready; incomplete outputs remain marked for review."
                              : "Bản thảo có thể gồm các mục phù hợp với phương pháp đã chọn. Bài chưa qua phản biện học thuật hay sẵn sàng xuất bản; kết quả chưa hoàn chỉnh sẽ được đánh dấu cần rà soát."}
                          </p>
                        </div>

                        {/* Deliverable 2: Multi-format Exports */}
                        <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                          <div className="flex items-center gap-2.5">
                            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-100 shrink-0">
                              <Download size={18} />
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-zinc-900">
                                {isEn ? "2. Downloadable Files" : "2. Tệp có thể tải xuống"}
                              </h4>
                              <span className="text-[11px] text-zinc-600 font-medium">{isEn ? "Formats available for this run" : "Định dạng khả dụng cho lượt chạy này"}</span>
                            </div>
                          </div>
                          <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                            {isEn
                              ? "Download supported formats such as Word, Markdown, or research packages when available. Export formatting does not establish venue compliance or publication readiness."
                              : "Tải các định dạng được hỗ trợ như Word, Markdown hoặc gói nghiên cứu khi có. Định dạng tệp không chứng minh bài đã đúng yêu cầu hội thảo/tạp chí hay sẵn sàng xuất bản."}
                          </p>
                        </div>

                        {/* Deliverable 3: Grounded Evidence & Citations */}
                        <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                          <div className="flex items-center gap-2.5">
                            <div className="p-2 rounded-lg bg-purple-50 text-purple-700 border border-purple-100 shrink-0">
                              <Layers size={18} />
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-zinc-900">
                                {isEn ? "3. Traceable Evidence & Citations" : "3. Bằng chứng trích dẫn có thể truy vết"}
                              </h4>
                              <span className="text-[11px] text-zinc-600 font-medium">{isEn ? "Source links where evidence is available" : "Liên kết nguồn khi có bằng chứng"}</span>
                            </div>
                          </div>
                          <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                            {isEn
                              ? "Claims can be traced to stored sources and passages where available. A citation does not prove that a source entails the claim, that coverage is complete, or that the draft is error-free."
                              : "Có thể truy vết luận điểm về nguồn và đoạn trích đã lưu khi dữ liệu sẵn có. Việc có trích dẫn không chứng minh nguồn hỗ trợ đầy đủ luận điểm, phạm vi tài liệu đã đầy đủ hay bản thảo không còn lỗi."}
                          </p>
                        </div>

                        {/* Deliverable 4: Protocol or Empirical Data */}
                        <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                          <div className="flex items-center gap-2.5">
                            <div className="p-2 rounded-lg bg-amber-50 text-amber-700 border border-amber-100 shrink-0">
                              <Activity size={18} />
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-zinc-900">
                                {isEn ? "4. Recorded Execution & Experiment Data" : "4. Dữ liệu thực thi và thực nghiệm đã ghi nhận"}
                              </h4>
                              <span className="text-[11px] text-zinc-600 font-medium">{isEn ? "Progress and artifacts where recorded" : "Tiến độ và hiện vật khi được ghi nhận"}</span>
                            </div>
                          </div>
                          <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                            {isEn
                              ? "View recorded progress, usage, metrics, and artifacts where available. Reproducing a result depends on preserved inputs, code, configuration, and execution environment."
                              : "Xem tiến độ, mức sử dụng, chỉ số và hiện vật đã được ghi nhận khi có. Tái lập kết quả còn phụ thuộc vào việc lưu đủ dữ liệu đầu vào, mã, cấu hình và môi trường thực thi."}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: RETRIEVED SOURCES */}
            {activeTab === 'sources' && (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-zinc-900">{isEn ? "Retrieved Literature & Sources" : "Nguồn tài liệu đã thu thập"} ({sources.length})</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">{isEn ? "Websites, scientific papers, and private documents gathered and indexed by AI agents." : "Các website, bài báo khoa học và tài liệu được Agent tìm kiếm và lập chỉ mục."}</p>
                  </div>
                  <div className="relative w-full sm:w-72">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                    <input
                      value={sourceSearch}
                      onChange={e => setSourceSearch(e.target.value)}
                      placeholder={isEn ? "Search sources..." : "Tìm trong nguồn..."}
                      className="w-full pl-9 pr-4 py-2 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                    />
                  </div>
                </div>

                {/* PDF Ingestion Card (SRS FR-02 & Private Artifact Grounding) */}
                <Card className="p-6 sm:p-7 border-dashed border-2 border-zinc-300 bg-white hover:border-zinc-400 transition-colors rounded-2xl shadow-xs">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <UploadCloud size={20} className="text-zinc-700" />
                        <h3 className="font-bold text-base sm:text-lg text-zinc-900">{isEn ? "Upload Private Grounding PDF" : "Tải lên tài liệu PDF riêng tư (Private Grounding)"}</h3>
                      </div>
                      <p className="text-xs text-zinc-500 leading-relaxed">
                        {isEn ? "Text is extracted, chunked, and embedded into pgvector as reliable grounding evidence for AI Agents (max 5 files, < 20MB, < 100 pages)." : "Hệ thống sẽ trích xuất văn bản, băm nhỏ chunk, lập chỉ mục pgvector và tích hợp làm bằng chứng tin cậy cho AI Agents (tối đa 5 file, < 20MB, < 100 trang)." }
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
                        {isUploading ? (isEn ? 'Uploading PDF...' : 'Đang nạp PDF...') : (isEn ? 'Upload PDF' : 'Tải lên PDF')}
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
                    {sourcesError} <button className="underline ml-2" onClick={() => void loadSources()}>{isEn ? "Retry" : "Thử lại"}</button>
                  </div>
                )}

                {sources.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {isWorking ? (isEn ? 'Agents are searching and reviewing literature...' : 'Agent đang tìm kiếm và duyệt nguồn...') : (isEn ? 'No literature sources saved for this research project yet.' : 'Chưa có nguồn tài liệu nào được lưu cho bài nghiên cứu này.')}
                  </Card>
                ) : filteredSources.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {isEn ? `No sources match keyword "${sourceSearch}".` : `Không tìm thấy nguồn tài liệu phù hợp với từ khóa "${sourceSearch}".`}
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {filteredSources.map((source) => (
                      <Card key={source.id} className="p-5 space-y-3 hover:border-zinc-300 transition-colors flex flex-col justify-between">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 border border-zinc-200">
                              [{source.source_tag}]
                            </span>
                            <Badge variant="outline">{source.source_type}</Badge>
                            {source.ingestion_status && (
                              <Badge variant={source.ingestion_status === 'READY' ? 'success' : source.ingestion_status === 'FAILED' ? 'danger' : source.ingestion_status === 'PROCESSING' ? 'default' : 'outline'}>
                                {source.ingestion_status === 'PROCESSING' && <Loader2 size={11} className="mr-1 inline animate-spin" />}
                                {source.ingestion_status}
                              </Badge>
                            )}
                            {source.relevance_score > 0 && (
                              <span className="text-xs text-emerald-600 font-medium">
                                {isEn ? "Relevance: " : "Liên quan: "}{(source.relevance_score * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-zinc-400">{formatDate(source.created_at)}</span>
                        </div>

                        <div>
                          {source.source_type === 'PDF' ? (
                            <div className="flex flex-col gap-2">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-base text-zinc-900">{source.title || (isEn ? 'Internal PDF Document' : 'Tài liệu PDF nội bộ')}</span>
                                <Badge variant="purple">{isEn ? "Private Document" : "Tài liệu riêng"}</Badge>
                              </div>
                              {(() => {
                                const matchingArt = artifacts.find(a => source.url.includes(a.file_path.split('/').pop() || '') || a.file_path.includes(source.title || ''));
                                if (matchingArt) {
                                  return (
                                    <div className="pt-1">
                                      <button
                                        type="button"
                                        onClick={() => handleDownloadArtifact(matchingArt.id, matchingArt.file_path.split('/').pop() || 'document.pdf')}
                                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-200 transition-colors cursor-pointer"
                                      >
                                        <Download size={13} className="text-purple-600" />
                                        <span>{isEn ? "Download Original PDF" : "Tải PDF gốc"} ({(matchingArt.file_size_bytes / 1024 / 1024).toFixed(2)} MB)</span>
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
                          <div className="text-xs font-mono text-zinc-600 mt-1 truncate">{source.url}</div>
                        </div>

                        {(source.venue || source.search_provider || source.doi) && (
                          <div className="text-xs text-zinc-500 flex flex-wrap items-center gap-2">
                            {source.search_provider && (
                              <span className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 border border-zinc-200 font-medium">
                                {source.search_provider}
                              </span>
                            )}
                            {source.venue && <span className="italic">{source.venue}</span>}
                            {source.doi && <span className="font-mono text-zinc-400">DOI: {source.doi}</span>}
                          </div>
                        )}

                        {source.ingestion_status === 'FAILED' && (
                          <div className="p-3 bg-red-50/80 border border-red-200 rounded-lg text-xs space-y-2">
                            <div className="flex items-start gap-2 text-red-700">
                              <AlertTriangle size={14} className="shrink-0 mt-0.5 text-red-600" />
                              <div className="flex-1">
                                <span className="font-semibold">{isEn ? 'Ingestion Failed: ' : 'Trích xuất thất bại: '}</span>
                                <span className="text-red-600">{source.ingestion_error || (isEn ? 'Unknown extraction error.' : 'Lỗi trích xuất không xác định.')}</span>
                              </div>
                            </div>
                            <Button
                              variant="danger-outline"
                              className="!h-8 !px-3 text-xs"
                              onClick={() => void handleRetrySource(source.id)}
                              isLoading={retryingSourceId === source.id}
                            >
                              <RefreshCw size={12} className="mr-1.5" />
                              {isEn ? 'Retry Ingestion' : 'Thử lại trích xuất'}
                            </Button>
                          </div>
                        )}

                        {source.content_snippet && (
                          <p className="text-sm leading-relaxed text-zinc-700 bg-zinc-50 p-3.5 rounded-xl border border-zinc-200 line-clamp-4">
                            {source.content_snippet}
                          </p>
                        )}

                        {source.attribution && (
                          <div className="text-xs text-zinc-500 border-t border-zinc-100 pt-2 flex items-center justify-between">
                            <span>{isEn ? "Attribution: " : "Tác quyền: "}{source.attribution}</span>
                            {source.license_name && <span>{isEn ? "License: " : "Giấy phép: "}{source.license_name}</span>}
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: EVIDENCE & CITATIONS */}
            {activeTab === 'citations' && (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-zinc-900">{isEn ? "Linked Evidence & Citations" : "Bằng chứng & Trích dẫn có nguồn"} ({citations.length})</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {isEn ? "Each citation is anchored to an indexed literature chunk and corresponding claim in the paper." : "Mỗi trích dẫn được neo chặt vào đoạn trích nguồn (chunk) và luận điểm (claim) tương ứng trong bài báo."}
                  </p>
                </div>

                {citationsError && (
                  <div className="text-sm text-red-600 bg-red-50 p-4 rounded-xl border border-red-200">
                    {citationsError} <button className="underline ml-2" onClick={() => void loadCitations()}>{isEn ? "Retry" : "Thử lại"}</button>
                  </div>
                )}

                {citations.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(task.status)
                      ? (isEn ? "No verified citations recorded for this project yet." : "Chưa có trích dẫn đã xác minh cho bài này.")
              : (isEn ? "Citations will appear when the pipeline extracts verified claims." : "Trích dẫn sẽ xuất hiện khi pipeline hoàn thành trích xuất bằng chứng.")}
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {citations.map((citation) => {
                      const isHighlighted = highlightedRef && (citation.citation_label.includes(highlightedRef) || String(citation.citation_number) === highlightedRef);
                      return (
                        <Card
                          key={citation.id}
                          className={`p-5 space-y-3 transition-all flex flex-col justify-between ${isHighlighted ? 'ring-2 ring-blue-500 bg-blue-50/30' : 'hover:border-zinc-300'}`}
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 border border-zinc-200">
                                {citation.citation_label || `[${citation.citation_number ?? '?'}]`}
                              </span>
                              {citation.source_url ? (
                                <a
                                  href={citation.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs font-medium text-blue-600 hover:underline inline-flex items-center gap-1 max-w-xs sm:max-w-sm truncate"
                                >
                                  <span className="truncate">{citation.source_title || citation.source_url}</span>
                                  <ExternalLink size={12} className="shrink-0" />
                                </a>
                              ) : (
                                <span className="text-xs text-zinc-400">{isEn ? "No source link" : "Không có liên kết nguồn"}</span>
                              )}
                            </div>

                            {citation.claim_text && (
                              <div className="text-sm sm:text-base text-zinc-900 font-semibold leading-relaxed">
                                <span className="text-zinc-500 font-normal">{isEn ? "Verified Claim: " : "Luận điểm xác minh: "}</span>
                                {citation.claim_text}
                              </div>
                            )}

                            {citation.chunk_content && (
                              <blockquote className="text-sm text-zinc-800 border-l-4 border-blue-500 pl-4 py-2.5 italic bg-zinc-50 rounded-r-xl leading-relaxed border-t border-b border-r border-zinc-200/60">
                                &ldquo;{citation.chunk_content}&rdquo;
                              </blockquote>
                            )}
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: AGENT RUNS & COST */}
            {activeTab === 'runs' && (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                {/* KPI Overview */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Total Cost" : "Tổng chi phí"}</span>
                    <div className="text-xl font-bold text-zinc-900 font-mono">${Number(task.total_cost_usd).toFixed(4)}</div>
                    <span className="text-xs text-zinc-700 font-medium">{isEn ? "Estimated USD" : "USD ước tính"}</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Total Tokens" : "Tổng Tokens"}</span>
                    <div className="text-xl font-bold text-zinc-900 font-mono">{task.total_tokens_used.toLocaleString('vi-VN')}</div>
                    <span className="text-xs text-zinc-700 font-medium">Input + Output</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Agent Runs" : "Lượt chạy Agent"}</span>
                    <div className="text-xl font-bold text-zinc-900">{runs.length}</div>
                    <span className="text-xs text-zinc-700 font-medium">{isEn ? "Recorded" : "Đã ghi nhận"}</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Completion Time" : "Thời gian hoàn tất"}</span>
                    <div className="text-sm font-semibold text-zinc-800 line-clamp-1 mt-1">
                      {task.completed_at ? formatDate(task.completed_at, language) : isWorking ? (isEn ? 'Running...' : 'Đang thực thi...') : (isEn ? 'Not completed' : 'Chưa hoàn tất')}
                    </div>
                    <span className="text-xs text-zinc-700 font-medium">{isEn ? "Attempt #" : "Lần chạy #"}{task.attempt_number}</span>
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
                      <h3 className="font-semibold text-zinc-900 text-base">{isEn ? "No agent runs recorded yet" : "Chưa có lượt chạy agent nào"}</h3>
                      <p className="text-sm text-zinc-500 mt-1">
                        {isEn ? "When the research pipeline executes, individual agent steps, tokens, and estimated costs will display here." : "Khi bài nghiên cứu bắt đầu chạy, tiến trình từng agent cùng token và chi phí sẽ hiển thị chi tiết tại đây."}
                      </p>
                    </div>
                  </Card>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-bold text-zinc-900">{isEn ? "Agent Execution Sequence" : "Chi tiết chuỗi thực thi tác tử"}</h2>
                      <span className="text-xs text-zinc-500">{runs.length} {isEn ? "runs" : "tác tử"}</span>
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
                                      {isEn ? "Iteration" : "Vòng"} {run.iteration}
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
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-zinc-50/90 p-3.5 sm:p-4 rounded-xl border border-zinc-200/80">
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">Tokens Input:</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">{run.input_tokens.toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">Tokens Output:</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">{run.output_tokens.toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">{isEn ? "Total Tokens:" : "Tổng Tokens:"}</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">{(run.input_tokens + run.output_tokens).toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">{isEn ? "Estimated Cost:" : "Chi phí ước tính:"}</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">${Number(run.estimated_cost).toFixed(6)}</div>
                                </div>
                              </div>

                              {/* Summaries */}
                              {(Object.keys(run.input_summary || {}).length > 0 || Object.keys(run.output_summary || {}).length > 0) && (
                                <div className="space-y-2 pt-1 text-sm">
                                  {Object.keys(run.output_summary || {}).length > 0 && (
                                    <div className="text-zinc-700 flex flex-wrap items-center gap-2">
                                      <span className="font-semibold text-zinc-800 text-sm">{isEn ? "Agent Output: " : "Kết quả đầu ra: "}</span>
                                      <span className="font-mono text-sm text-zinc-900 bg-zinc-100 px-2 py-1 rounded-md border border-zinc-200/60">
                                        {JSON.stringify(run.output_summary)}
                                      </span>
                                    </div>
                                  )}
                                  {run.tool_calls && run.tool_calls.length > 0 && (
                                    <div className="text-zinc-700 flex flex-wrap items-center gap-2">
                                      <span className="font-semibold text-zinc-800 text-sm">{isEn ? "Tools Executed: " : "Công cụ đã gọi: "}</span>
                                      <span className="font-mono text-zinc-800 flex flex-wrap gap-1.5">
                                        {run.tool_calls.map((tc, idx) => (
                                          <span key={idx} className="inline-block px-2 py-0.5 rounded-md bg-zinc-100 text-zinc-900 border border-zinc-200 font-mono text-xs sm:text-sm font-medium">
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
                                  <strong>{isEn ? "Error: " : "Lỗi: "}</strong>{run.error_message}
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

            {/* TAB 5: STUDY PROTOCOL (GATE G4) */}
            {activeTab === 'protocol' && (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-zinc-200 pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-zinc-900 flex items-center gap-2">
                      <FlaskConical size={18} className="text-indigo-600" />
                      {isEn ? "Study Protocol" : "Đề cương nghiên cứu (Study Protocol)"}
                    </h2>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      {isEn ? "Intermediate methodological artifact designed by the Methodologist Agent" : "Văn bản trung gian (Intermediate Artifact) được thiết kế bởi Agent Methodologist"}
                    </p>
                  </div>
                  {task.protocol_artifact_id && (
                    <Button
                      variant="outline"
                      onClick={() => void handleDownloadArtifact(task.protocol_artifact_id!, 'study_protocol.md')}
                    >
                      <Download size={14} className="mr-1.5" /> {isEn ? "Download (.md)" : "Tải về (.md)"}
                    </Button>
                  )}
                </div>

                {protocolError && (
                  <div className="p-4 bg-red-50 text-red-700 text-xs rounded-xl border border-red-200">
                    {protocolError}
                  </div>
                )}

                {protocol?.content_markdown ? (
                  <Card className="p-8 sm:p-12 bg-white shadow-xs">
                    <MarkdownViewer content={protocol.content_markdown} academicStyle={true} />
                  </Card>
                ) : (
                  <div className="p-8 text-center text-zinc-400">{isEn ? "Loading study protocol..." : "Đang tải nội dung đề cương nghiên cứu..."}</div>
                )}
              </div>
            )}

            {/* TAB 6: METADATA & CONFIG */}
            {activeTab === 'details' && (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                <Card className="p-6 space-y-5">
                  <h2 className="text-lg font-bold text-zinc-900 border-b border-zinc-200 pb-3">{isEn ? "Task Configuration & Metadata" : "Cấu hình & Chi tiết nhiệm vụ"}</h2>
                  <ModelConnectionSummary key={task.id} task={task} isEn={isEn} />

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-semibold text-zinc-700">{isEn ? "Research Question:" : "Câu hỏi nghiên cứu:"}</span>
                      <p className="text-zinc-900 mt-1 leading-relaxed bg-zinc-50 p-3 rounded-xl border border-zinc-200">
                        {task.research_question}
                      </p>
                    </div>

                    <div>
                      <span className="font-semibold text-zinc-700">{isEn ? "Additional Description:" : "Mô tả bổ sung:"}</span>
                      <p className="text-zinc-600 mt-1 leading-relaxed bg-zinc-50 p-3 rounded-xl border border-zinc-200">
                        {task.description || (isEn ? 'No additional description provided' : 'Không có mô tả bổ sung')}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm border-t border-zinc-100 pt-4">
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Research Type" : "Loại nghiên cứu"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">
                        {task.research_type === 'EMPIRICAL_HUMAN' ? (isEn ? 'Fieldwork' : 'Thực địa') : task.research_type === 'EMPIRICAL_COMPUTATIONAL' ? (isEn ? 'Computational' : 'Tính toán') : (isEn ? 'Literature Review' : 'Tổng quan')}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Research Depth" : "Độ sâu nghiên cứu"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.research_depth}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Report Length" : "Độ dài báo cáo"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.report_length}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Citation Style" : "Kiểu trích dẫn"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.citation_style}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm border-t border-zinc-100 pt-4">
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Plan Approval (HITL)" : "Duyệt kế hoạch (HITL)"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.require_plan_approval ? (isEn ? 'Enabled' : 'Bật') : (isEn ? 'Disabled' : 'Tắt')}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Max Iterations" : "Vòng lặp tối đa"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.max_iterations}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Max Sources" : "Nguồn tối đa"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.max_sources}</div>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-500">{isEn ? "Attempt Number" : "Lần chạy thử lại"}</span>
                      <div className="font-semibold text-zinc-800 mt-0.5">{task.attempt_number}</div>
                    </div>
                  </div>

                  {task.user_data_submission && (
                    <div className="border-t border-zinc-100 pt-4">
                      <h3 className="font-semibold text-zinc-900 text-sm mb-2 flex items-center gap-1.5">
                        <FlaskConical size={14} className="text-indigo-600" />
                        {isEn ? "Submitted Empirical / Fieldwork Data" : "Dữ liệu thực nghiệm đã cung cấp"}
                      </h3>
                      <div className="bg-zinc-50 p-4 rounded-xl border border-zinc-200 text-xs space-y-2">
                        {task.user_data_submission.sample_size != null && (
                          <div className="flex justify-between">
                            <span className="text-zinc-500">{isEn ? "Actual Sample Size:" : "Cỡ mẫu thực tế:"}</span>
                            <span className="font-semibold text-zinc-800">{task.user_data_submission.sample_size}</span>
                          </div>
                        )}
                        {task.user_data_submission.data_provenance && (
                          <div className="flex justify-between">
                            <span className="text-zinc-500">{isEn ? "Data Provenance:" : "Xuất xứ / Nguồn:"}</span>
                            <span className="font-semibold text-zinc-800">{task.user_data_submission.data_provenance}</span>
                          </div>
                        )}
                        {task.user_data_submission.method_notes && (
                          <div>
                            <span className="text-zinc-500 font-medium">{isEn ? "Methodology & Tools:" : "Phương pháp & công cụ:"}</span>
                            <p className="text-zinc-700 mt-0.5">{task.user_data_submission.method_notes}</p>
                          </div>
                        )}
                        <div>
                          <span className="text-zinc-500 font-medium">{isEn ? "Findings Summary:" : "Tóm tắt kết quả:"}</span>
                          <p className="text-zinc-800 font-medium mt-0.5 whitespace-pre-wrap">{task.user_data_submission.results_summary}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="border-t border-zinc-100 pt-4 flex flex-wrap items-center justify-between text-xs text-zinc-500 gap-2">
                    <span>{isEn ? "Created: " : "Tạo lúc: "}{formatDate(task.created_at, language)}</span>
                    {task.completed_at && <span>{isEn ? "Completed: " : "Hoàn thành lúc: "}{formatDate(task.completed_at, language)}</span>}
                    <Link className="underline hover:text-zinc-900" href="/dashboard">{isEn ? "Back to Dashboard" : "Quay lại danh sách bài"}</Link>
                  </div>
                </Card>

                {/* Danger Zone */}
                <div className="rounded-2xl border border-red-200 bg-red-50/50 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-red-900">{isEn ? "Danger Zone" : "Vùng nguy hiểm"}</h3>
                    <p className="text-xs text-red-700 mt-0.5">{isEn ? "Permanently delete this research project and all associated sources, citations, and artifacts." : "Xóa vĩnh viễn bài nghiên cứu này cùng toàn bộ nguồn và trích dẫn liên quan."}</p>
                  </div>
                  <Button variant="danger" onClick={() => void handleDeleteTask()} isLoading={isDeleting}>
                    <Trash2 size={15} className="mr-1.5" /> {isEn ? "Delete Research Project" : "Xóa bài nghiên cứu"}
                  </Button>
                </div>
              </div>
            )}

            {/* TAB 7: COMPUTATIONAL EXPERIMENTS & JOURNAL */}
            {activeTab === 'experiments' && (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                {/* 1. DATASET MANAGEMENT CARD */}
                <Card className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-100 pb-4">
                    <div>
                      <h2 className="font-semibold text-zinc-900 text-base flex items-center gap-2">
                        <Database size={18} className="text-blue-600" />
                        {isEn ? "Experimental Dataset (Dataset CSV)" : "Tập dữ liệu thực nghiệm (Dataset CSV)"}
                      </h2>
                      <p className="text-xs text-zinc-500 mt-1">
                        {isEn ? <>Provide tabular numeric CSV dataset for computational routine <code className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-800 font-mono">tabular_regression_v1</code>.</> : <>Cung cấp tệp CSV dữ liệu số phục vụ routine tính toán <code className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-800 font-mono">tabular_regression_v1</code>.</>}
                      </p>
                    </div>
                    <div>
                      <input
                        ref={datasetFileInputRef}
                        type="file"
                        accept=".csv"
                        onChange={handleUploadDataset}
                        className="hidden"
                      />
                      <Button
                        variant="outline"
                        onClick={() => datasetFileInputRef.current?.click()}
                        disabled={isUploadingDataset || task.status === 'RUNNING'}
                        className="text-xs"
                      >
                        <UploadCloud size={14} className="mr-1.5" />
                        {isUploadingDataset ? (isEn ? 'Uploading...' : 'Đang tải lên...') : (isEn ? 'Upload Dataset (.csv)' : 'Tải lên tập dữ liệu (.csv)')}
                      </Button>
                    </div>
                  </div>

                  {datasetUploadError && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
                      <XCircle size={14} className="shrink-0" />
                      <span>{datasetUploadError}</span>
                    </div>
                  )}

                  {datasetUploadSuccess && (
                    <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
                      <CheckCircle2 size={14} className="shrink-0 text-emerald-600" />
                      <span>{datasetUploadSuccess}</span>
                    </div>
                  )}

                  {/* Artifacts with DATASET_CSV */}
                  {(() => {
                    const dsArtifact = artifacts.find(a => a.export_type === 'DATASET_CSV');
                    return (
                      <div className="mt-4 p-4 rounded-xl bg-zinc-50 border border-zinc-200/80 text-xs">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div>
                            <span className="font-semibold text-zinc-800">
                              {dsArtifact ? (isEn ? `Dataset: ${dsArtifact.file_path.split('/').pop()}` : `Tập dữ liệu: ${dsArtifact.file_path.split('/').pop()}`) : (isEn ? 'Data Mode: Standard synthetic benchmark dataset (50 samples, seed 42)' : 'Chế độ dữ liệu: Tự động sinh tập benchmark số đối chuẩn (50 mẫu, seed 42)')}
                            </span>
                            <p className="text-zinc-500 text-[11px] mt-0.5">
                              {dsArtifact
                                ? (isEn ? `Size: ${(dsArtifact.file_size_bytes / 1024).toFixed(1)} KB` : `Dung lượng: ${(dsArtifact.file_size_bytes / 1024).toFixed(1)} KB`)
                                : (isEn ? 'System automatically uses standardized benchmark data if no custom dataset is provided.' : 'Hệ thống tự động sử dụng tập dữ liệu chuẩn hóa nếu bạn không tải lên tệp tùy chỉnh.')}
                            </p>
                          </div>
                          {dsArtifact && (
                            <a
                              href={api.tasks.getArtifactDownloadUrl(task.id, dsArtifact.id)}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100 font-medium text-xs self-start sm:self-auto"
                            >
                              <Download size={13} /> {isEn ? "Download CSV" : "Tải CSV"}
                            </a>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </Card>

                {/* 2. LATEST EXPERIMENT RUN & METRICS COMPARISON */}
                {experiments.length > 0 ? (
                  experiments.map((exp, idx) => {
                    const m = exp.metrics || {};
                    const baseM = m.baseline || {};
                    const modelM = m.model || {};
                    const comp = m.comparison || {};
                    const verdict = comp.verdict;
                    const reproStatus = exp.reproducibility_status;

                    return (
                      <Card key={exp.id || idx} className="p-6 space-y-5">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-100 pb-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <h2 className="font-semibold text-zinc-900 text-base">
                                Routine: <code className="font-mono text-indigo-700">{exp.routine_name}</code>
                              </h2>
                              <Badge variant="outline" className="text-xs">
                                {exp.status}
                              </Badge>
                            </div>
                            <p className="text-xs text-zinc-500 mt-1 font-mono">
                              Checksum: {exp.input_checksum ? exp.input_checksum.slice(0, 16) + '...' : 'N/A'} • {exp.manifest.valid_rows || exp.manifest.dataset_rows || 50} {isEn ? 'samples' : 'mẫu'} • Split 80/20 (seed 42)
                            </p>
                          </div>
                          <div>
                            {reproStatus === 'PASSED' ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-medium border border-emerald-200">
                                <CheckCircle2 size={13} className="text-emerald-600" />
                                {isEn ? "Repeatability check PASSED (abs diff ≤ 10⁻⁸)" : "Tái lập kiểm chứng ĐẠT (abs diff ≤ 10⁻⁸)"}
                              </span>
                            ) : reproStatus === 'FAILED' ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-100 text-red-800 text-xs font-medium border border-red-200">
                                <XCircle size={13} className="text-red-600" />
                                {isEn ? "Repeatability check FAILED" : "Tái lập kiểm chứng THẤT BẠI"}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-100 text-zinc-600 text-xs font-medium">
                                {isEn ? "Repeatability not checked" : "Chưa kiểm tái lập"}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Comparative Metrics Table */}
                        <div>
                          <h3 className="text-xs font-semibold text-zinc-700 uppercase tracking-wider mb-2">
                            {isEn ? "Scientific Empirical Benchmarks" : "Bảng đo lường đối chứng khoa học (Empirical Benchmarks)"}
                          </h3>
                          <div className="overflow-x-auto rounded-xl border border-zinc-200">
                            <table className="w-full text-xs text-left">
                              <thead className="bg-zinc-50 text-zinc-700 border-b border-zinc-200 font-medium">
                                <tr>
                                  <th className="py-2.5 px-4">{isEn ? "Model" : "Mô hình"}</th>
                                  <th className="py-2.5 px-4">{isEn ? "MAE (Primary Metric)" : "MAE (Chỉ số chính)"}</th>
                                  <th className="py-2.5 px-4">{isEn ? "RMSE (Secondary Metric)" : "RMSE (Chỉ số phụ)"}</th>
                                  <th className="py-2.5 px-4">{isEn ? "Coefficient of Determination R²" : "Hệ số xác định R²"}</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-zinc-200">
                                <tr className="hover:bg-zinc-50/50">
                                  <td className="py-2.5 px-4 font-medium text-zinc-800">
                                    Mean Baseline <span className="text-zinc-400 font-normal">({isEn ? "Sample Mean" : "Nghiệm trung bình"})</span>
                                  </td>
                                  <td className="py-2.5 px-4 font-mono">{baseM.mae != null ? baseM.mae.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono">{baseM.rmse != null ? baseM.rmse.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono">{baseM.r2 != null ? baseM.r2.toFixed(6) : '—'}</td>
                                </tr>
                                <tr className="hover:bg-zinc-50/50 bg-indigo-50/20">
                                  <td className="py-2.5 px-4 font-medium text-indigo-900">
                                    Ridge Regression <span className="text-indigo-600 font-normal">(alpha=1.0)</span>
                                  </td>
                                  <td className="py-2.5 px-4 font-mono font-semibold text-indigo-900">{modelM.mae != null ? modelM.mae.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono text-indigo-900">{modelM.rmse != null ? modelM.rmse.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono text-indigo-900">{modelM.r2 != null ? modelM.r2.toFixed(6) : '—'}</td>
                                </tr>
                                <tr className="bg-zinc-50/80 font-medium">
                                  <td className="py-2.5 px-4 text-zinc-700">{isEn ? "Delta (Ridge - Baseline)" : "Chênh lệch (Delta: Ridge - Baseline)"}</td>
                                  <td className={`py-2.5 px-4 font-mono ${comp.delta_mae != null && comp.delta_mae < 0 ? 'text-emerald-700 font-semibold' : 'text-zinc-700'}`}>
                                    {comp.delta_mae != null ? (comp.delta_mae > 0 ? `+${comp.delta_mae.toFixed(6)}` : comp.delta_mae.toFixed(6)) : '—'}
                                  </td>
                                  <td className="py-2.5 px-4 font-mono text-zinc-700">
                                    {comp.delta_rmse != null ? (comp.delta_rmse > 0 ? `+${comp.delta_rmse.toFixed(6)}` : comp.delta_rmse.toFixed(6)) : '—'}
                                  </td>
                                  <td className="py-2.5 px-4 text-zinc-500">—</td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Verdict Card */}
                        {verdict && (
                          <div className={`p-4 rounded-xl border text-xs ${verdict === 'IMPROVEMENT' ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-amber-50 border-amber-200 text-amber-900'}`}>
                            <div className="flex items-center gap-2 font-semibold">
                              {verdict === 'IMPROVEMENT' ? (
                                <>
                                  <CheckCircle2 size={16} className="text-emerald-600" />
                                  <span>{isEn ? `Verdict: IMPROVEMENT — Ridge Regression reduced MAE error (${comp.pct_improvement ?? 0}% relative to baseline).` : `Kết luận: CẢI THIỆN (IMPROVEMENT) — Ridge Regression giảm sai số MAE (${comp.pct_improvement ?? 0}% so với baseline).`}</span>
                                </>
                              ) : (
                                <>
                                  <AlertTriangle size={16} className="text-amber-600" />
                                  <span>{isEn ? "Verdict: NO_IMPROVEMENT — Valid negative result integrity. Ridge regression did not outperform simple sample mean." : "Kết luận: KHÔNG CẢI THIỆN (NO_IMPROVEMENT) — Kết quả âm hợp lệ (Negative Result Integrity). Ridge regression không vượt trội hơn nghiệm trung bình đơn giản."}</span>
                                </>
                              )}
                            </div>
                            <p className="mt-1 text-[11px] opacity-80">
                              {isEn ? "Scientific Integrity Principle: All empirical measurements (whether improved or negative findings) are transparently recorded and included in the paper." : "Nguyên tắc tính toàn vẹn khoa học: Mọi kết quả đo lường (dù tốt hơn hay không cải thiện) đều được báo cáo minh bạch và đưa vào bản thảo bài báo."}
                            </p>
                          </div>
                        )}

                        {/* Non-causal Disclaimer */}
                        <div className="p-3 bg-zinc-50 rounded-xl border border-zinc-200 text-[11px] text-zinc-600">
                          {isEn ? <><strong>Scientific Limitation:</strong> Regression model measures predictive correlation on test splits (exploratory). Results must never be interpreted as causal relationships (non-causal).</> : <><strong>Giới hạn khoa học:</strong> Mô hình hồi quy đo lường mối tương quan và hiệu năng dự đoán trên tập kiểm thử (predictive/exploratory). Kết quả tuyệt đối không được suy luận thành quan hệ nhân quả (non-causal).</>}
                        </div>

                        {/* Experiment Artifacts */}
                        <div className="pt-2">
                          <h4 className="text-xs font-semibold text-zinc-700 mb-2">{isEn ? "Stored Experimental Artifacts" : "Tệp dữ liệu thực nghiệm đã lưu (Artifacts)"}</h4>
                          <div className="flex flex-wrap gap-2">
                            {artifacts
                              .filter(a => ['METRICS_JSON', 'MANIFEST_JSON', 'CHART_DATA_JSON', 'REPRO_README'].includes(a.export_type))
                              .map(art => (
                                <a
                                  key={art.id}
                                  href={api.tasks.getArtifactDownloadUrl(task.id, art.id)}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 text-xs font-mono"
                                >
                                  <Download size={12} />
                                  {art.file_path.split('/').pop()}
                                </a>
                              ))}
                          </div>
                        </div>
                      </Card>
                    );
                  })
                ) : (
                  <Card className="p-8 text-center text-zinc-500">
                    <FlaskConical size={32} className="mx-auto text-zinc-400 mb-2" />
                    <p className="text-sm font-medium text-zinc-700">{isEn ? "No computational routine results yet" : "Chưa có kết quả thực nghiệm tính toán"}</p>
                    <p className="text-xs text-zinc-500 mt-1">
                      {task.status === 'PENDING'
                        ? (isEn ? 'Click Start Research to launch the empirical benchmark pipeline.' : 'Nhấn Bắt đầu nghiên cứu để khởi chạy pipeline tính toán đối chuẩn.')
                        : (isEn ? 'Routine tabular_regression_v1 will run automatically during the pipeline.' : 'Routine tabular_regression_v1 sẽ tự động chạy trong luồng nghiên cứu.')}
                    </p>
                  </Card>
                )}

                {/* 3. SCIENTIFIC AUDIT JOURNAL TIMELINE */}
                {journal.length > 0 && (
                  <Card className="p-6">
                    <h3 className="font-semibold text-zinc-900 text-sm mb-4 flex items-center gap-2">
                      <Clock size={16} className="text-zinc-600" />
                      {isEn ? "Scientific Experiment Journal (Immutable Append-Only Audit Log)" : "Sổ nhật ký thí nghiệm nghiên cứu (Immutable Append-Only Journal)"}
                    </h3>
                    <div className="relative border-l-2 border-zinc-200 ml-3 space-y-6">
                      {journal.map(entry => {
                        const kindColors: Record<string, string> = {
                          PLAN_FROZEN: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          STARTED: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          EXECUTION_RESULT: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          OBSERVATION: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          REPRODUCTION_CHECK: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          INTERPRETATION: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                        };
                        const colorClass = kindColors[entry.kind] || 'border-zinc-200 bg-white text-zinc-800';

                        return (
                          <div key={entry.id} className="relative pl-6">
                            <span className="absolute -left-3 top-1 w-5 h-5 rounded-full border border-zinc-300 bg-white flex items-center justify-center text-[10px] font-bold text-zinc-700">
                              {entry.sequence}
                            </span>
                            <div className="space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border ${colorClass}`}>
                                  {entry.kind}
                                </span>
                                <span className="text-xs text-zinc-400 font-mono">
                                  {isEn ? "Agent: " : "Tác tử: "}<strong className="text-zinc-700">{entry.actor}</strong> • {formatDate(entry.created_at, language)}
                                </span>
                              </div>
                              {entry.payload && (
                                <div className="p-3 bg-zinc-50 rounded-lg text-xs font-mono text-zinc-700 overflow-x-auto mt-1 border border-zinc-200/60 leading-relaxed">
                                  {entry.payload.summary ? (
                                    <p className="font-sans text-zinc-800">{entry.payload.summary}</p>
                                  ) : (
                                    <pre className="text-[11px]">{JSON.stringify(entry.payload, null, 2)}</pre>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}
              </div>
            )}
          </div>
        </main>

        {/* Right Sidebar: Research Pipeline Stages */}
        <aside id="stages-sidebar" className={`${isRightSidebarCollapsed ? 'hidden' : 'w-full lg:w-72 xl:w-80'} border-l border-zinc-200 bg-zinc-50/70 flex flex-col shrink-0 overflow-y-auto max-h-72 lg:max-h-none transition-all duration-200 print:hidden`}>
          <div className="p-4 border-b border-zinc-200 flex items-center justify-between sticky top-0 bg-zinc-50/95 backdrop-blur z-10">
            <div className="flex items-center gap-2">
              <Activity size={17} className="text-zinc-700" />
              <h2 className="font-bold text-sm sm:text-base uppercase tracking-wider text-zinc-900">
                {isEn ? "Research Pipeline" : "Các giai đoạn nghiên cứu"}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setIsRightSidebarCollapsed(true)}
              className="hidden lg:block text-zinc-400 hover:text-zinc-700 transition-colors p-1.5 rounded-lg hover:bg-zinc-200/60"
              title={isEn ? "Collapse pipeline stages" : "Thu gọn cột giai đoạn"}
            >
              <PanelRightClose size={16} />
            </button>
          </div>

          <div className="p-4 flex-1 overflow-y-auto space-y-4">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                {isEn ? "Execution Stages" : "Tiến trình các bước"}
              </span>
              <Link
                href={`/research/${params.id}/monitor`}
                className="text-[11px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-0.5 hover:underline"
              >
                {isEn ? "Live Monitor →" : "Giám sát tác tử →"}
              </Link>
            </div>

            <div className="relative border-l-2 border-zinc-200 ml-3 space-y-5 my-2">
              {(() => {
                const currentStages = task.research_type === 'REVIEW'
                  ? REVIEW_STAGES
                  : task.research_type === 'EMPIRICAL_COMPUTATIONAL'
                  ? COMPUTATIONAL_STAGES
                  : BASE_STAGES;
                return currentStages.map((stage, index) => {
                  const state = stageState(currentStages, index, task.status, task.current_step);
                  const Icon = state === 'done' ? CheckCircle2 : state === 'active' ? Activity : state === 'review' ? AlertTriangle : state === 'failed' ? XCircle : state === 'paused' ? Clock : Circle;
                  return (
                    <div
                      key={isEn ? stage.title_en : stage.title_vi}
                      className={`relative pl-6 py-1 rounded-lg transition-colors ${
                        state === 'active' ? 'bg-blue-50/80 -mx-2 px-3 border border-blue-100' : ''
                      }`}
                    >
                      <span className={`absolute left-0 top-1.5 p-1 rounded-full border bg-white ${
                        state === 'done' ? 'text-emerald-500 border-emerald-200'
                        : state === 'active' ? 'text-blue-600 border-blue-300 shadow-sm shadow-blue-100'
                        : ['review', 'paused'].includes(state) ? 'text-amber-600 border-amber-300' : state === 'failed' ? 'text-red-600 border-red-300' : 'text-zinc-300 border-zinc-200'
                      }`}>
                        <Icon size={12} className={state === 'active' ? 'animate-pulse' : ''} />
                      </span>
                      <div>
                        <span className={`text-xs leading-snug block ${
                          state === 'waiting' ? 'text-zinc-400 font-normal'
                          : state === 'active' ? 'font-bold text-blue-900'
                          : 'font-medium text-zinc-700'
                        }`}>
                          {isEn ? stage.title_en : stage.title_vi}
                        </span>
                        {state === 'active' && (
                          <span className="text-[10px] text-blue-600 font-bold">
                            {isEn ? 'In progress…' : 'Đang thực hiện…'}
                          </span>
                        )}
                        {['review', 'failed', 'cancelled', 'paused'].includes(state) && (
                          <span className="text-[10px] text-amber-700 font-bold">{statusLabel(task.status, language)}</span>
                        )}
                        {state === 'done' && (
                          <span className="text-[10px] text-emerald-600 font-medium">
                            {isEn ? 'Completed' : 'Hoàn thành'}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>

            <div className="pt-3 border-t border-zinc-200/80">
              <Link
                href={`/research/${params.id}/monitor`}
                className="inline-flex items-center justify-center gap-1.5 w-full py-2.5 px-3 text-xs font-bold text-zinc-800 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors border border-zinc-200"
              >
                <Activity size={13} />
                {isEn ? "Open Live Monitor" : "Mở giám sát trực tiếp"}
              </Link>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
