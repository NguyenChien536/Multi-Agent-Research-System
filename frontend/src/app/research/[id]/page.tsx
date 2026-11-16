'use client';
import { ResearchErrorNotice } from '@/components/ResearchErrorNotice';
import { ResearchRecoveryNotice, researchBudgetBlocked } from '@/components/ResearchRecoveryNotice';
import { ModelSettingsPanel } from '@/components/ModelSettingsPanel';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  CheckCircle2, Circle, Clock, Check, Download,
  FileText, Globe, Layers, Play, RefreshCw,
  XCircle, Activity, Cpu, UploadCloud, FlaskConical,
  AlertTriangle, Maximize2, Minimize2, PanelLeftClose, PanelLeft, PanelRight, PanelRightClose,
  ListFilter, Bookmark, Info
} from 'lucide-react';
import { Badge } from '@/components/ui/Components';
import { Button } from '@/components/ui/Button';
import { extractHeadings } from '@/components/ui/MarkdownViewer';
import { ExperimentsPanel } from '@/components/research/ExperimentsPanel';
import { AgentRunsPanel } from '@/components/research/AgentRunsPanel';
import { SourcesPanel } from '@/components/research/SourcesPanel';
import { CitationsPanel } from '@/components/research/CitationsPanel';
import { PaperDocument } from '@/components/research/PaperDocument';
import { ResearchProgressPanel } from '@/components/research/ResearchProgressPanel';
import { ProtocolPanel } from '@/components/research/ProtocolPanel';
import { TaskDetailsPanel } from '@/components/research/TaskDetailsPanel';
import { useLanguage } from '@/lib/i18n';
import { useDialogFocus } from '@/lib/use-dialog-focus';
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
  const { language } = useLanguage();
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
  const runStatusFilter: 'ALL' | 'SUCCESS' | 'RUNNING' | 'FAILED' = 'ALL';
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [isStarting, setIsStarting] = useState(false);
  const [actionError, setActionError] = useState('');
  const [showModelSettings, setShowModelSettings] = useState(false);
  const settingsDialog = useDialogFocus(showModelSettings, () => { setShowModelSettings(false); setReloadKey(v => v + 1); });
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isWidePaper, setIsWidePaper] = useState(false);
  const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false);
  const [isRightSidebarCollapsed, setIsRightSidebarCollapsed] = useState(false);
  useEffect(() => {
    const narrow = window.matchMedia?.('(max-width: 1023px)');
    if (!narrow) return;
    const collapseOnSmallScreen = () => {
      if (narrow.matches) { setIsLeftSidebarCollapsed(true); setIsRightSidebarCollapsed(true); }
    };
    collapseOnSmallScreen();
    narrow.addEventListener('change', collapseOnSmallScreen);
    return () => narrow.removeEventListener('change', collapseOnSmallScreen);
  }, []);

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
    if (!task || isStarting || isCancelling) return;
    if (researchBudgetBlocked(task)) return;
    if (task.status !== 'PENDING' && task.status !== 'FAILED' && !window.confirm(isEn
      ? 'Run research again? Saved reports and files are kept. This starts a new workflow and uses the remaining article allowance.'
      : 'Chạy lại nghiên cứu? Bài viết và tệp đã lưu được giữ lại. Lượt mới sử dụng phần ngân sách còn lại của bài.')) return;
    setIsStarting(true);
    setActionError('');
    try {
      if (task.status === 'FAILED') await api.tasks.retry(task.id);
      else await api.tasks.start(task.id);
      setReloadKey(v => v + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to start research.' : 'Không thể bắt đầu nghiên cứu.'));
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancelTask = async () => {
    if (!task || isCancelling || isStarting) return;
    if (!confirm(isEn ? 'Are you sure you want to cancel this research task?' : 'Bạn có chắc chắn muốn hủy bài nghiên cứu này?')) return;
    setIsCancelling(true);
    setActionError('');
    try {
      await api.tasks.cancel(task.id);
      setReloadKey(v => v + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to cancel research.' : 'Không thể hủy bài nghiên cứu.'));
    } finally {
      setIsCancelling(false);
    }
  };

  const handleExtendAllowance = async () => {
    if (!task?.token_allowance?.can_extend || isStarting || isCancelling) return;
    setIsStarting(true);
    setActionError('');
    try {
      await api.tasks.retry(task.id, {max_input_tokens:task.token_allowance.next_input_tokens,
        max_output_tokens:task.token_allowance.next_output_tokens,
        max_llm_calls:task.token_allowance.next_max_llm_calls,
        timeout_seconds:task.token_allowance.next_timeout_seconds,
        max_cost_usd:task.token_allowance.next_max_cost_usd});
      setReloadKey(v => v + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to extend token allowance.' : 'Không thể tăng hạn mức token.'));
    } finally {
      setIsStarting(false);
    }
  };

  const handleDeleteTask = async () => {
    if (!task) return;
    if (!confirm(isEn ? 'Are you sure you want to permanently delete this research project?' : 'Bạn có chắc chắn muốn xóa bài nghiên cứu này vĩnh viễn?')) return;
    setIsDeleting(true);
    setActionError('');
    try {
      await api.tasks.delete(task.id);
      router.push('/dashboard');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to delete research project.' : 'Không thể xóa bài nghiên cứu.'));
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
    setActionError('');
    try {
      await api.tasks.retrySource(task.id, sourceId);
      await loadSources();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Failed to retry ingestion' : 'Không thể thử lại trích xuất'));
    } finally {
      setRetryingSourceId(null);
    }
  };

  const handleDownloadArtifact = async (artifactId: string, filename: string) => {
    if (!task) return;
    setActionError('');
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
      setActionError(err instanceof Error ? err.message : (isEn ? 'Download error' : 'Lỗi tải xuống'));
    }
  };

  const handleCopyMarkdown = () => {
    if (!report?.content_markdown) return;
    setActionError('');
    void navigator.clipboard.writeText(report.content_markdown).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }).catch(() => setActionError(isEn ? 'Clipboard unavailable. Download Markdown instead.' : 'Không sao chép được. Hãy tải bản Markdown.'));
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
    setActionError('');
      await exportPaperToDocx({
        title: report.title,
        markdownContent: report.content_markdown,
        completedAt: formatDate(report.created_at),
        researchType: task.research_type,
        filename: task.title
      });
    } catch (err) {
      console.error('Docx export error:', err);
      setActionError(isEn ? 'Unable to generate Word file (.docx). Please try again or download Markdown.' : 'Không thể tạo file Word (.docx). Vui lòng thử lại hoặc tải tệp Markdown.');
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
    setActionError('');
    try {
      await api.tasks.approvePlan(task.id, {
        plan_version: task.plan_version,
        approved_queries: editableQueries.filter(q => q.trim().length > 0),
      });
      setReloadKey(v => v + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to approve research plan.' : 'Không thể duyệt kế hoạch.'));
    } finally {
      setIsApprovingPlan(false);
    }
  };

  const handleRejectPlan = async () => {
    if (!task) return;
    const reason = prompt(isEn ? 'Enter revision instructions or feedback for the Supervisor Agent:' : 'Nhập lý do từ chối hoặc hướng dẫn điều chỉnh cho Supervisor:') || '';
    if (!reason.trim()) return;
    setIsRejectingPlan(true);
    setActionError('');
    try {
      await api.tasks.rejectPlan(task.id, { plan_version: task.plan_version, reason: reason.trim() });
      setReloadKey(v => v + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to reject research plan.' : 'Không thể từ chối kế hoạch.'));
    } finally {
      setIsRejectingPlan(false);
    }
  };

  const handleResumeWithData = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task) return;
    setActionError('');
    const parsedSize = Number(sampleSize.trim());
    if (!Number.isSafeInteger(parsedSize) || parsedSize < 1) {
      setActionError(isEn ? 'Please enter a valid sample size (integer >= 1).' : 'Vui lòng nhập cỡ mẫu thực tế hợp lệ (số nguyên lớn hơn hoặc bằng 1).');
      return;
    }
    if (methodNotes.trim().length < 10) {
      setActionError(isEn ? 'Please describe data collection methodology and procedures (at least 10 characters).' : 'Vui lòng mô tả phương pháp và quy trình thu thập dữ liệu (tối thiểu 10 ký tự).');
      return;
    }
    if (resultsSummary.trim().length < 10) {
      setActionError(isEn ? 'Please summarize empirical findings / collected data (at least 10 characters).' : 'Vui lòng nhập tóm tắt kết quả thực nghiệm / thực địa (tối thiểu 10 ký tự).');
      return;
    }
    if (!resultArtifactId || dataProvenance.trim().length < 10 || isUploadingResult) {
      setResultFileError(isEn ? 'Select an uploaded result file and describe data provenance (at least 10 characters).' : 'Chọn tệp kết quả đã tải lên và mô tả nguồn gốc dữ liệu (ít nhất 10 ký tự).');
      return;
    }
    setIsResumingData(true);
    setActionError('');
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
      setActionError(err instanceof Error ? err.message : (isEn ? 'Unable to resume research.' : 'Không thể tiếp tục bài nghiên cứu.'));
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

  const sourceProps = {
    task, sources, artifacts, isEn, isWorking, sourcesError, loadSources,
    handleFileUpload, handleDownloadArtifact, handleRetrySource,
    retryingSourceId, isUploading, uploadError, setUploadError,
    uploadSuccess, setUploadSuccess, fileInputRef, formatDate, sourceSearch, setSourceSearch,
  };
  const citationProps = { task, citations, citationsError, loadCitations, isEn, highlightedRef };
  const paperDocumentProps = {
    task, report: report!, isEn, language, isCopied, isWidePaper,
    isDownloadMenuOpen, setIsDownloadMenuOpen, isExportingDocx,
    onCopyMarkdown: handleCopyMarkdown, onToggleWidePaper: handleToggleWidePaper,
    onDownloadDocx: handleDownloadDocx, onDownloadMarkdown: handleDownloadMarkdown,
    onDownloadBundle: handleDownloadBundle,
    onCitationClick: (label: string) => { setHighlightedRef(label); setActiveTab('citations'); },
    statusLabel, formatDate,
  };
  const progressPanelProps = {
    task, isEn, language, isWorking, isStarting,
    sourceCount: sources.length, citationCount: citations.length, runCount: runs.length,
    onStartTask: handleStartTask, onRefresh: () => setReloadKey(v => v + 1),
    statusLabel, stepLabel,
  };
  const protocolPanelProps = {
    task, isEn, protocol, protocolError, onDownloadArtifact: handleDownloadArtifact,
  };
  const detailsPanelProps = {
    task, isEn, language, isDeleting, onDeleteTask: handleDeleteTask, formatDate,
  };

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden bg-white print:h-auto print:overflow-visible print:bg-white print:block">
      {/* Top Header Bar */}
      <div id="research-header-bar" className="min-h-16 px-6 py-3 border-b border-stone-200/80 bg-white/90 backdrop-blur-md flex flex-wrap items-center justify-between gap-3 shrink-0 print:hidden">
        <div className="flex items-center gap-3 flex-1 basis-80 min-w-0">
          <button
            type="button"
            onClick={() => setIsLeftSidebarCollapsed(prev => !prev)}
            aria-controls="toc-sidebar"
            aria-expanded={!isLeftSidebarCollapsed}
            aria-label={isEn ? 'Toggle contents' : 'Bật/tắt mục lục'}
            className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 border border-stone-200/90 rounded-full text-xs font-medium text-stone-700 hover:text-stone-950 hover:bg-stone-100 transition-colors shrink-0 shadow-2xs"
            title={isLeftSidebarCollapsed ? (isEn ? "Show table of contents" : "Hiện mục lục bài báo") : (isEn ? "Collapse table of contents" : "Thu gọn mục lục")}
          >
            {isLeftSidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
            <span>{isEn ? 'Contents' : 'Mục lục'}</span>
          </button>
          <div className="min-w-0">
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
                  {task.research_type === 'EMPIRICAL_COMPUTATIONAL' ? (isEn ? 'Awaiting CSV dataset' : 'Chờ tập dữ liệu CSV') : (isEn ? 'Awaiting field data upload' : 'Chờ tải lên dữ liệu')}
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
        <div className="flex flex-wrap items-center gap-2" aria-label={isEn ? 'Research controls' : 'Thao tác bài nghiên cứu'}>
          {task.token_allowance?.can_extend && <Button variant="success" onClick={() => {
            setActiveTab('report');
            setTimeout(() => document.querySelector('#research-recovery-controls')?.scrollIntoView({behavior:'smooth',block:'center'}), 0);
          }}>{isEn ? 'Review token allowance' : 'Xem hạn mức để tiếp tục'}</Button>}
          {researchBudgetBlocked(task) && !task.token_allowance?.can_extend && <Button onClick={() => router.push('/')}>
            {isEn ? 'Create new research' : 'Tạo nghiên cứu mới'}
          </Button>}
          {!researchBudgetBlocked(task) && !task.token_allowance?.can_extend && ['PENDING', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW'].includes(task.status) && (
            <Button
              variant={task.status === 'CANCELLED' ? 'primary' : 'success'}
              onClick={() => void handleStartTask()}
              isLoading={isStarting}
            >
              <Play size={15} className="mr-1.5" /> {task.status === 'FAILED' ? (isEn ? 'Continue from failed step' : 'Tiếp tục từ bước lỗi') : task.status !== 'PENDING' ? (isEn ? 'Start another run' : 'Bắt đầu lượt mới') : (isEn ? 'Start Research' : 'Bắt đầu nghiên cứu')}
            </Button>
          )}

          {canCancel && (
            <Button variant="danger-outline" onClick={() => void handleCancelTask()} isLoading={isCancelling}>
              <XCircle size={15} className="mr-1.5" /> {isEn ? 'Stop research' : 'Dừng nghiên cứu'}
            </Button>
          )}
          <Button variant="outline" onClick={() => setShowModelSettings(true)}>{isEn ? 'API & model' : 'API & model'}</Button>
          <Button variant="outline" aria-controls="stages-sidebar" aria-expanded={!isRightSidebarCollapsed}
            onClick={() => setIsRightSidebarCollapsed(v => !v)}>
            <PanelRight size={15} className="mr-1.5" />{isRightSidebarCollapsed ? (isEn ? 'Show pipeline' : 'Mở tiến trình') : (isEn ? 'Hide pipeline' : 'Ẩn tiến trình')}
          </Button>
          <Button variant="outline" onClick={() => setReloadKey(v => v + 1)} aria-label={isEn ? "Refresh" : "Làm mới"}>
            <RefreshCw size={15} />
          </Button>
        </div>
      </div>
      {actionError && <div role="alert" className="flex items-center justify-between gap-3 border-b border-red-200 bg-red-50 px-6 py-3 text-sm text-red-800"><span>{actionError}</span><button type="button" onClick={()=>setActionError('')} aria-label={isEn?'Dismiss error':'Đóng thông báo lỗi'}><XCircle size={18} /></button></div>}
      {showModelSettings && <div role="dialog" aria-modal="true" aria-label="API & model" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div ref={settingsDialog} tabIndex={-1} className="max-h-[90dvh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl outline-none">
          <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">API & model</h2>
            <Button variant="outline" onClick={() => { setShowModelSettings(false); setReloadKey(v => v + 1); }}>{isEn ? 'Close' : 'Đóng'}</Button></div>
          <ModelSettingsPanel isEn={isEn} taskId={task.id} />
        </div>
      </div>}

      {/* Main Workspace Body */}
      <div className="relative flex min-h-0 flex-1 overflow-hidden flex-col lg:flex-row print:overflow-visible print:h-auto print:block">
        {/* Stages Sidebar */}
        {/* Left Sidebar: Table of Contents & Manuscript Details */}
        <aside id="toc-sidebar" className={`${isLeftSidebarCollapsed ? 'hidden' : 'w-80 max-w-full lg:w-72 xl:w-80'} absolute inset-y-0 left-0 z-30 lg:relative lg:inset-auto lg:z-auto border-r border-stone-200/80 bg-white flex flex-col shrink-0 overflow-y-auto shadow-lg lg:shadow-none transition-all duration-200 print:hidden`}>
          <div className="p-4 border-b border-stone-200/80 flex items-center justify-between sticky top-0 bg-white/95 backdrop-blur z-10">
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
              aria-label={isEn ? "Collapse table of contents" : "Thu gọn mục lục"}
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
                      <span className="text-xs sm:text-sm font-bold text-zinc-800 uppercase tracking-wide">
                        {isEn ? "Sections" : "Các đề mục"}
                      </span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-900 font-bold">
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
                            h.level === 1 ? 'font-bold text-zinc-950 text-sm' :
                            h.level === 2 ? 'pl-4 font-semibold text-zinc-900 text-[13px] sm:text-sm' :
                            'pl-6 font-medium text-zinc-800 text-xs sm:text-[13px]'
                          } hover:bg-zinc-200/80 hover:text-zinc-950 ${activeTocSlug === h.slug ? 'bg-stone-100 shadow-xs text-stone-950 font-bold border-l-2 border-stone-900' : ''}`}
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
                <div className="p-4 text-xs sm:text-sm text-zinc-600 leading-relaxed italic">
                  {report
                    ? (isEn ? "Draft contains no section headings." : "Bản thảo chưa phân mục.")
                    : (isEn ? "Table of contents will appear once manuscript draft is generated." : "Mục lục sẽ hiển thị khi bản thảo bài báo được tạo.")
                  }
                </div>
              );
            })()}

            {/* Draft Details (Thông tin bản thảo) */}
            <div className="p-4 space-y-3.5 text-xs sm:text-sm">
              <div className="flex items-center gap-1.5 pb-2 border-b border-zinc-200">
                <Bookmark size={15} className="text-zinc-800" />
                <h3 className="font-bold text-xs sm:text-sm uppercase tracking-wide text-zinc-900">
                  {isEn ? "Draft Details" : "Thông tin bản thảo"}
                </h3>
              </div>

              {report && (
                <div className="space-y-2.5 text-zinc-800">
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-600 font-medium">{isEn ? "Word count:" : "Số lượng từ:"}</span>
                    <strong className="font-bold text-zinc-950 font-mono text-xs sm:text-sm">{report.word_count.toLocaleString()} {isEn ? "words" : "từ"}</strong>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-600 font-medium">{isEn ? "Reading time:" : "Thời gian đọc:"}</span>
                    <strong className="font-bold text-zinc-950 font-mono text-xs sm:text-sm">~{Math.max(1, Math.ceil((report.word_count || 1) / 220))} {isEn ? "min" : "phút"}</strong>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-600 font-medium">{isEn ? "Sources cited:" : "Nguồn tài liệu:"}</span>
                    <span className="font-bold text-zinc-950">{sources.length} {isEn ? "sources" : "nguồn"}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-600 font-medium">{isEn ? "Linked citations:" : "Trích dẫn có nguồn:"}</span>
                    <span className="font-bold text-zinc-950">{citations.length} {isEn ? "claims" : "đoạn"}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-600 font-medium">{isEn ? "Citation style:" : "Kiểu trích dẫn:"}</span>
                    <Badge variant="outline">{task.citation_style}</Badge>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-zinc-100">
                    <span className="text-zinc-600 font-medium text-xs sm:text-sm">{isEn ? "Reading mode:" : "Chế độ đọc:"}</span>
                    <button
                      type="button"
                      onClick={handleToggleWidePaper}
                      className="text-blue-700 hover:text-blue-900 font-bold cursor-pointer text-xs sm:text-sm hover:underline flex items-center gap-1"
                    >
                      {isWidePaper ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                      <span>{isWidePaper ? (isEn ? "Standard width" : "Thu gọn về chuẩn") : (isEn ? "Full width" : "Phóng to toàn màn hình ↗")}</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Research Metadata */}
              <div className={`space-y-2 text-zinc-700 ${report ? 'pt-3 border-t border-zinc-200' : ''}`}>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-600 font-medium">{isEn ? "Research Type:" : "Loại nghiên cứu:"}</span>
                  <Badge variant="outline">
                    {task.research_type === 'EMPIRICAL_HUMAN' ? (isEn ? 'Fieldwork' : 'Thực địa') : task.research_type === 'EMPIRICAL_COMPUTATIONAL' ? (isEn ? 'Computational' : 'Tính toán') : (isEn ? 'Literature Review' : 'Tổng quan')}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-600 font-medium">{isEn ? "Tokens used:" : "Tokens tiêu thụ:"}</span>
                  <strong className="font-bold text-zinc-950 font-mono text-xs sm:text-sm">{task.total_tokens_used.toLocaleString('vi-VN')}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-600 font-medium">{isEn ? "Estimated cost:" : "Chi phí ước tính:"}</span>
                  <strong className="font-bold text-zinc-950 font-mono text-xs sm:text-sm">${Number(task.total_cost_usd).toFixed(4)}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-600 font-medium">{isEn ? "Updated:" : "Cập nhật:"}</span>
                  <span className="text-zinc-900 font-medium text-xs">{formatDate(task.updated_at, language)}</span>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Content Tabs Area */}

        {/* Content Tabs Area */}
        <main className="flex min-h-0 flex-1 flex-col bg-white overflow-hidden print:overflow-visible print:h-auto print:block">
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
            <div id="fieldwork-section" className="p-4 bg-indigo-50 border-b border-indigo-200 text-sm print:hidden shrink-0">
              <h2 className="font-semibold">{isEn ? 'Upload your CSV to continue' : 'Tải CSV để tiếp tục'}</h2>
              <p className="my-2">{isEn ? 'Numeric columns and a target column are required. A valid upload resumes this article automatically.' : 'CSV cần các cột số và cột đích target. Tệp hợp lệ sẽ tự tiếp tục bài này.'}</p>
              <input type="file" accept=".csv" aria-label={isEn ? 'Upload computational CSV' : 'Tải CSV tính toán'} disabled={isUploadingDataset} onChange={handleUploadDataset} className="block w-full text-sm" />
              {isUploadingDataset && <p role="status">{isEn ? 'Uploading…' : 'Đang tải…'}</p>}
              {datasetUploadError && <p role="alert" className="mt-2 text-red-700">{datasetUploadError}</p>}
              {datasetUploadSuccess && <p role="status" className="mt-2 text-emerald-700">{datasetUploadSuccess}</p>}
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

                    <div id="research-tab-bar" className="flex border-b border-stone-200 px-4 sm:px-6 bg-white shrink-0 gap-2 overflow-x-auto no-scrollbar print:hidden">
            <button
              onClick={() => setActiveTab('report')}
              className={`px-5 py-3.5 text-base sm:text-[17px] border-b-2 -mb-[2px] whitespace-nowrap transition-all duration-150 flex items-center gap-2 ${
                activeTab === 'report'
                  ? 'border-zinc-950 text-zinc-950 bg-white font-extrabold shadow-xs'
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
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
                    : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
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
                    : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
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
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
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
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
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
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
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
                  : 'border-transparent text-zinc-600 hover:text-zinc-950 hover:bg-stone-100/60 font-bold'
              }`}
            >
              <Info size={18} className={activeTab === 'details' ? 'text-zinc-950' : 'text-zinc-500'} />
              <span>{isEn ? 'Metadata & Config' : 'Thông tin & Cấu hình'}</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 bg-white print:overflow-visible print:h-auto print:p-0 print:m-0 print:bg-white print:block">
            {/* TAB 1: SCIENTIFIC PAPER */}
            <ResearchRecoveryNotice task={task} isEn={isEn} busy={isStarting} onContinue={() => void handleStartTask()} onExtend={() => void handleExtendAllowance()} />
            {task.writing_progress && !report && <p role="status" className="mb-4 text-sm text-zinc-700">
              {isEn ? 'Writing groups saved: ' : 'Nhóm phần đã lưu: '}{task.writing_progress.completed}/{task.writing_progress.total}
            </p>}
            {(task.status === 'FAILED' || task.current_step === 'BUDGET_LIMIT') && <ResearchErrorNotice isEn={isEn}
              step={task.failed_agent || (task.current_step ? stepLabel(task.current_step, language) : null)}
              error={task.current_step === 'BUDGET_LIMIT' ? 'TASK_BUDGET_LIMIT' : task.latest_error || runs.filter(run => run.status === 'FAILED' && run.attempt_number === task.attempt_number).at(-1)?.error_message} />}
            {activeTab === 'report' && (
              <div className={`paper-space w-full ${isWidePaper ? 'max-w-6xl' : 'max-w-4xl'} mx-auto space-y-6 transition-all duration-300 print:max-w-none print:m-0 print:p-0 print:space-y-0`}>
                {(['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW', 'FAILED'].includes(task.status) || report?.research_task_id === params.id) ? report?.research_task_id === params.id ? (
                  <PaperDocument {...paperDocumentProps} />
                ) : (
                  <div className="text-center py-12 text-zinc-600">
                    {isEn ? 'No saved manuscript is available yet.' : 'Chưa có bản thảo được lưu.'}
                    {reportError && <button className="underline ml-2" onClick={() => void loadReport()}>{isEn ? 'Check for saved draft' : 'Kiểm tra bản thảo đã lưu'}</button>}
                  </div>
                ) : (
                  <ResearchProgressPanel {...progressPanelProps} />
                )}
              </div>
            )}

            {/* TAB 2: RETRIEVED SOURCES */}
            {activeTab === 'sources' && <SourcesPanel {...sourceProps} />}

            {/* TAB 3: EVIDENCE & CITATIONS */}
            {activeTab === 'citations' && <CitationsPanel {...citationProps} />}

            {/* TAB 4: AGENT RUNS & COST */}
            {activeTab === 'runs' && <AgentRunsPanel task={task} runs={runs} runsError={runsError} runStatusFilter={runStatusFilter} isWorking={isWorking} isEn={isEn} language={language} formatDate={formatDate} />}

            {/* TAB 5: STUDY PROTOCOL (GATE G4) */}
            {activeTab === 'protocol' && <ProtocolPanel {...protocolPanelProps} />}

            {/* TAB 6: METADATA & CONFIG */}
            {activeTab === 'details' && <TaskDetailsPanel {...detailsPanelProps} />}

            {/* TAB 7: COMPUTATIONAL EXPERIMENTS & JOURNAL */}
            {activeTab === 'experiments' && <ExperimentsPanel task={task} artifacts={artifacts} experiments={experiments} journal={journal} isEn={isEn} language={language} formatDate={formatDate} datasetFileInputRef={datasetFileInputRef} handleUploadDataset={handleUploadDataset} isUploadingDataset={isUploadingDataset} datasetUploadError={datasetUploadError} datasetUploadSuccess={datasetUploadSuccess} />}
          </div>
        </main>

        {/* Right Sidebar: Research Pipeline Stages */}
        <aside id="stages-sidebar" className={`${isRightSidebarCollapsed ? 'hidden' : 'w-80 max-w-full lg:w-72 xl:w-80'} absolute inset-y-0 right-0 z-30 lg:relative lg:inset-auto lg:z-auto border-l border-stone-200/80 bg-white flex flex-col shrink-0 overflow-y-auto shadow-lg lg:shadow-none transition-all duration-200 print:hidden`}>
          <div className="p-4 border-b border-stone-200/80 flex items-center justify-between sticky top-0 bg-white/95 backdrop-blur z-10">
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
              aria-label={isEn ? "Collapse pipeline stages" : "Thu gọn cột giai đoạn"}
            >
              <PanelRightClose size={16} />
            </button>
          </div>

          <div className="p-4 flex-1 overflow-y-auto space-y-4">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs sm:text-sm font-bold text-zinc-800 uppercase tracking-wide">
                {isEn ? "Execution Stages" : "Tiến trình các bước"}
              </span>
              <Link
                href={`/research/${params.id}/monitor`}
                className="text-xs font-bold text-blue-700 hover:text-blue-900 flex items-center gap-0.5 hover:underline"
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
                        <span className={`text-[13px] sm:text-sm leading-snug block ${
                          state === 'waiting' ? 'text-zinc-500 font-medium'
                          : state === 'active' ? 'font-bold text-blue-950'
                          : 'font-semibold text-zinc-900'
                        }`}>
                          {isEn ? stage.title_en : stage.title_vi}
                        </span>
                        {state === 'active' && (
                          <span className="text-xs text-blue-700 font-bold">
                            {isEn ? 'In progress…' : 'Đang thực hiện…'}
                          </span>
                        )}
                        {['review', 'failed', 'cancelled', 'paused'].includes(state) && (
                          <span className="text-xs text-amber-800 font-bold">{statusLabel(task.status, language)}</span>
                        )}
                        {state === 'done' && (
                          <span className="text-xs text-emerald-700 font-semibold">
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
                className="inline-flex items-center justify-center gap-1.5 w-full py-2.5 px-3 text-xs sm:text-sm font-bold text-zinc-900 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors border border-zinc-200"
              >
                <Activity size={13} />
                {isEn ? "Open Live Monitor" : "Mở giám sát trực tiếp"}
              </Link>
            </div>
          </div>
        </aside>
        {isRightSidebarCollapsed && (
          <div className="hidden lg:flex w-12 shrink-0 flex-col items-center border-l border-stone-200/80 bg-white py-3 print:hidden">
            <button type="button" aria-controls="stages-sidebar" aria-expanded={false}
              aria-label={isEn ? 'Open research pipeline' : 'Mở cột tiến trình nghiên cứu'}
              onClick={() => setIsRightSidebarCollapsed(false)}
              className="flex items-center gap-3 rounded-lg px-2 py-3 text-xs font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 [writing-mode:vertical-rl]"
              title={isEn ? 'Open research pipeline' : 'Mở cột tiến trình nghiên cứu'}>
              <PanelRight size={17} />{isEn ? 'Pipeline' : 'Tiến trình'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
