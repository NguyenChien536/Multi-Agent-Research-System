'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  Activity, ArrowLeft, ArrowUpRight, AlertTriangle, CheckCircle2, Circle, Clock,
  FileText, ExternalLink, ChevronLeft, ChevronRight, Info,
  BookOpen, FileCheck, AlertCircle, RefreshCw
} from 'lucide-react';
import { api } from '@/lib/api';
import { currentStage, stagesFor, stageKey, activityStage, outputLabel, statusLabel } from '@/lib/monitoring';
import { useMonitorPoll } from '@/lib/use-monitor-poll';
import { PollStatus, StatusPill, formatTime } from '@/components/monitoring/MonitorUI';
import { PipelineFlow } from '@/components/monitoring/PipelineFlow';
import { useLanguage } from '@/lib/i18n';

interface ActionItem {
  title: string;
  text: string;
  button: string;
  tone: 'amber' | 'blue' | 'red' | 'emerald' | 'zinc';
}

const ACTIONS_EN: Record<string, ActionItem> = {
  REVIEW_PLAN: {
    title: 'Research plan is awaiting your approval',
    text: 'Supervisor proposed initial search queries and section outlines. You can approve or adjust the research scope in the workspace.',
    button: 'Review & Approve Plan',
    tone: 'amber'
  },
  UPLOAD_DATA: {
    title: 'Awaiting empirical fieldwork dataset',
    text: 'Methodologist completed protocol. Please upload survey data or results to proceed. In the meantime, this task is saved and you can work on other projects.',
    button: 'Upload Data',
    tone: 'amber'
  },
  START_RESEARCH: {
    title: 'Research has not been started yet',
    text: 'Review the question, custom documents, and configuration before starting execution.',
    button: 'Start Research',
    tone: 'blue'
  },
  CHECK_FAILURE: {
    title: 'Execution halted due to an issue',
    text: 'Inspect the latest step and activity log below. You can open the task to retry or modify settings.',
    button: 'Inspect Error',
    tone: 'red'
  },
  CANCELLED: {
    title: 'Research was paused / cancelled',
    text: 'All retrieved sources, citations, and previous drafts remain intact. You can resume at any time.',
    button: 'View Research',
    tone: 'zinc'
  },
  REVIEW_LIMIT: {
    title: 'Halted due to resource ceiling',
    text: 'Budget or maximum iteration limit was reached. Check current artifacts before proceeding.',
    button: 'Review Task',
    tone: 'amber'
  },
  REVIEW_REPORT: {
    title: 'Draft ready for review',
    text: 'Internal AI critique is recorded. Open the workspace to inspect the draft, citations, and remaining findings.',
    button: 'Review Draft',
    tone: 'blue'
  },
  REVIEW_RUN: {
    title: 'Review execution cycle',
    text: 'Completed execution cycle. Check stages and generated artifacts.',
    button: 'View Research',
    tone: 'amber'
  },
  READ_REPORT: {
    title: 'Scientific report completed',
    text: 'All stages finished successfully. You can open workspace to read full draft, verify evidence, and export to DOCX/PDF/Markdown.',
    button: 'Read Report',
    tone: 'emerald'
  },
  REPORT_UNAVAILABLE: {
    title: 'Report draft not found',
    text: 'Task completion status and stored report data did not match. Open task to inspect saved outputs.',
    button: 'Inspect Task',
    tone: 'amber'
  },
  WAIT: {
    title: 'System is processing in background',
    text: 'Agents are running autonomously. You can safely switch to another project; progress and artifacts are saved automatically.',
    button: 'Open Workspace',
    tone: 'blue'
  },
};

const ACTIONS_VI: Record<string, ActionItem> = {
  REVIEW_PLAN: {
    title: 'Kế hoạch nghiên cứu đang chờ bạn duyệt',
    text: 'Supervisor đã lập đề cương và truy vấn tìm kiếm. Bạn có thể duyệt tiếp hoặc gửi góp ý điều chỉnh hướng nghiên cứu trong workspace.',
    button: 'Xem & Duyệt kế hoạch',
    tone: 'amber'
  },
  UPLOAD_DATA: {
    title: 'Đang chờ bạn nạp dữ liệu thực địa',
    text: 'Methodologist đã thiết lập protocol. Vui lòng tải lên tệp dữ liệu CSV/JSON hoặc khảo sát để tiếp tục. Trong lúc chờ, bài nghiên cứu vẫn được lưu và bạn có thể chạy bài khác.',
    button: 'Mở bài và nạp dữ liệu G4',
    tone: 'amber'
  },
  START_RESEARCH: {
    title: 'Bài nghiên cứu chưa được kích hoạt',
    text: 'Kiểm tra câu hỏi nghiên cứu, tệp tài liệu riêng và cấu hình mô hình trước khi cho agent bắt đầu hoạt động.',
    button: 'Mở bài & Bắt đầu nghiên cứu',
    tone: 'blue'
  },
  CHECK_FAILURE: {
    title: 'Lần thực hiện này đã dừng do phát sinh lỗi',
    text: 'Xem bước gần nhất và nhật ký hoạt động bên dưới để xác định tác tử gặp sự cố. Bạn có thể mở bài nghiên cứu để chạy lại hoặc sửa cấu hình.',
    button: 'Mở bài để xử lý lỗi',
    tone: 'red'
  },
  CANCELLED: {
    title: 'Nghiên cứu đã được chủ động dừng / hủy',
    text: 'Toàn bộ dữ liệu, nguồn trích dẫn và các bản nháp trước đó vẫn được giữ nguyên vẹn. Bạn có thể kích hoạt lại bài nghiên cứu bất cứ lúc nào.',
    button: 'Xem lại bài nghiên cứu',
    tone: 'zinc'
  },
  REVIEW_LIMIT: {
    title: 'Đã dừng do chạm trần giới hạn tài nguyên',
    text: 'Hệ thống ghi nhận nghiên cứu đã đạt ngân sách tối đa hoặc vượt số lượt token/vòng lặp cho phép. Hãy kiểm tra các kết quả hiện có trong bài.',
    button: 'Kiểm tra bài nghiên cứu',
    tone: 'amber'
  },
  REVIEW_REPORT: {
    title: 'Bản thảo bài báo cần bạn kiểm tra và phản biện',
    text: 'Agent Critic đã có nhận xét. Hãy mở bài để đọc nội dung bài báo khoa học, đối chiếu trích dẫn và quyết định xuất bản.',
    button: 'Kiểm tra bản thảo bài báo',
    tone: 'blue'
  },
  REVIEW_RUN: {
    title: 'Cần kiểm tra lần thực hiện này',
    text: 'Chưa ghi nhận bản thảo hoàn chỉnh sau chu kỳ. Hãy xem chi tiết các bước xử lý và bằng chứng đã thu thập được.',
    button: 'Mở bài nghiên cứu',
    tone: 'amber'
  },
  READ_REPORT: {
    title: 'Bản thảo nghiên cứu khoa học đã hoàn thành',
    text: 'Tất cả các chặng đã hoàn tất thành công. Bạn có thể mở bài để đọc bài báo hoàn chỉnh, tra cứu cây bằng chứng và tải tệp Markdown/DOCX/PDF.',
    button: 'Đọc bản thảo hoàn chỉnh',
    tone: 'emerald'
  },
  REPORT_UNAVAILABLE: {
    title: 'Chưa tìm thấy bản thảo bài báo đã lưu',
    text: 'Trạng thái hoàn thành và dữ liệu báo cáo chưa đồng bộ. Vui lòng mở lại bài nghiên cứu để kiểm tra kết quả lưu trữ.',
    button: 'Mở bài nghiên cứu',
    tone: 'amber'
  },
  WAIT: {
    title: 'Hệ thống tác tử AI đang tiếp tục xử lý ngầm',
    text: 'Các tác tử đang phối hợp làm việc tự động. Bạn hoàn toàn có thể chuyển sang nghiên cứu bài khác; tiến trình và kết quả sẽ tự động lưu lại.',
    button: 'Mở Workspace bài viết',
    tone: 'blue'
  },
};

export default function ResearchMonitorPage() {
  const { id } = useParams<{ id: string }>();
  const { language, t } = useLanguage();

  const [historyPage, setHistoryPage] = useState({ taskId: id, offset: 0 });
  const offset = historyPage.taskId === id ? historyPage.offset : 0;

  const load = useCallback((signal: AbortSignal) => api.tasks.getMonitor(id, offset, 20, signal), [id, offset]);
  const { data, error, errorStatus, loading, lastSuccess, refresh } = useMonitorPoll(load, 4000);

  const snapshot = data?.task_id === id ? data : null;
  const actionsDict = language === 'en' ? ACTIONS_EN : ACTIONS_VI;
  const action = snapshot ? (actionsDict[snapshot.next_action] || actionsDict.WAIT) : null;
  const current = currentStage(snapshot?.current_step);
  const activeStages = stagesFor(snapshot?.research_type);
  const activeStageKey = stageKey(snapshot?.current_step);

  const isEn = language === 'en';
  const router = useRouter();

  return (
    <main className="h-full overflow-y-auto bg-zinc-50/60 p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-[1720px] mx-auto space-y-6">

        {/* Not Found / Access Denied — Friendly Empty State */}
        {!loading && !snapshot && (
          <div className="flex flex-col items-center justify-center gap-6 rounded-2xl border border-zinc-200 bg-white p-12 sm:p-16 text-center shadow-xs">
            <div className="w-16 h-16 rounded-2xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
              <FileText size={28} className="text-zinc-400" />
            </div>
            <div className="max-w-md space-y-2">
              <h2 className="text-lg font-semibold text-zinc-900">
                {errorStatus === 404
                  ? (isEn ? 'Research project not found' : 'Không tìm thấy bài nghiên cứu')
                  : errorStatus === 401
                  ? (isEn ? 'Session expired' : 'Phiên đăng nhập đã hết hạn')
                  : errorStatus === 403
                  ? (isEn ? 'Access denied' : 'Không có quyền truy cập')
                  : (isEn ? 'Unable to load project' : 'Không thể tải dữ liệu bài nghiên cứu')}
              </h2>
              <p className="text-sm text-zinc-500 leading-relaxed">
                {errorStatus === 404
                  ? (isEn
                    ? 'This research project may have been deleted, or the link is outdated. Head to your Dashboard to view all your projects.'
                    : 'Bài nghiên cứu này có thể đã bị xoá hoặc đường dẫn không còn hợp lệ. Hãy quay về Dashboard để xem toàn bộ dự án của bạn.')
                  : errorStatus === 401
                  ? (isEn
                    ? 'Your session has expired. Please log in again to continue.'
                    : 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.')
                  : errorStatus === 403
                  ? (isEn
                    ? 'You do not have permission to view this research project.'
                    : 'Bạn không có quyền xem bài nghiên cứu này.')
                  : (error || (isEn ? 'An unexpected error occurred while loading this task.' : 'Đã có lỗi xảy ra khi tải bài nghiên cứu này.'))}
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-3">
              {errorStatus === 401 ? (
                <button
                  type="button"
                  onClick={() => router.push('/login')}
                  className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 transition-colors shadow-2xs cursor-pointer"
                >
                  {isEn ? 'Sign in again' : 'Đăng nhập lại'}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => router.push('/dashboard')}
                    className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 transition-colors shadow-2xs cursor-pointer"
                  >
                    {isEn ? 'Go to Dashboard' : 'Về Dashboard'}
                  </button>
                  <button
                    type="button"
                    onClick={() => router.push('/')}
                    className="inline-flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-5 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors cursor-pointer"
                  >
                    {isEn ? 'Create New Research' : 'Tạo bài nghiên cứu mới'}
                  </button>
                  <button
                    type="button"
                    onClick={() => router.push('/research/monitor')}
                    className="inline-flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-5 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors cursor-pointer"
                  >
                    {isEn ? 'View all monitors' : 'Tất cả tiến độ'}
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {/* Loading Initial State */}
        {loading && !snapshot && (
          <div role="status" className="flex items-center justify-center gap-2.5 rounded-2xl border border-zinc-200 bg-white p-16 text-center text-sm font-medium text-zinc-600 shadow-2xs">
            <RefreshCw size={20} className="animate-spin text-blue-600" />
            <span>{isEn ? 'Loading monitoring status...' : 'Đang tải dữ liệu tiến độ từ máy chủ...'}</span>
          </div>
        )}

        {/* Loaded Content */}
        {snapshot && action && (
          <>
            {/* Top Header Card */}
            <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white p-5 sm:p-6 rounded-2xl border border-zinc-200 shadow-xs">
              <div className="min-w-0 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-zinc-100 text-zinc-700 uppercase tracking-wider">
                    {snapshot.research_type === 'REVIEW'
                      ? (isEn ? 'Literature Review' : 'Tổng quan lý thuyết')
                      : snapshot.research_type === 'EMPIRICAL_COMPUTATIONAL'
                      ? (isEn ? 'Computational Empirical' : 'Thực nghiệm tính toán')
                      : snapshot.research_type === 'EMPIRICAL_HUMAN'
                      ? (isEn ? 'Fieldwork' : 'Thực nghiệm con người')
                      : (isEn ? 'Research Project' : 'Đề tài nghiên cứu')}
                  </span>
                  {snapshot.workflow && (
                    <>
                      <span className="text-zinc-300">•</span>
                      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-700">
                        {t('mon_detail_run')} #{snapshot.workflow.run_number}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-700">
                        {t('mon_detail_plan')}{snapshot.workflow.plan_version}
                      </span>
                    </>
                  )}
                </div>

                <h1 className="break-words text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
                  {snapshot.title}
                </h1>

                {snapshot.workflow && (
                  <p className="text-xs text-zinc-600 flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span>{t('mon_detail_started')}: <strong className="font-normal text-zinc-800">{formatTime(snapshot.workflow.started_at, language)}</strong></span>
                    {snapshot.workflow.completed_at && (
                      <>
                        <span className="text-zinc-300">•</span>
                        <span>{t('mon_detail_completed')}: <strong className="font-normal text-zinc-800">{formatTime(snapshot.workflow.completed_at, language)}</strong></span>
                      </>
                    )}
                    <span className="text-zinc-300">•</span>
                    <span>{t('mon_detail_sample')}: <strong className="font-normal text-zinc-800">{formatTime(snapshot.observed_at, language)}</strong></span>
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                <StatusPill status={snapshot.status} />
                <Link
                  href={`/research/${id}`}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-zinc-900 px-5 text-sm font-bold text-white hover:bg-zinc-800 transition-all shadow-sm hover:shadow-md active:scale-[0.99]"
                >
                  <FileText size={14} />
                  <span>{t('nav_workspace')}</span>
                  <ArrowUpRight size={13} />
                </Link>
              </div>
            </header>

            {/* Polling & Sync Status Banner */}
            <PollStatus error={error} lastSuccess={lastSuccess} refresh={refresh} />

            {/* Worker Lease Expired Alert Box */}
            {snapshot.worker_lease_expired && (
              <div role="alert" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs sm:text-sm text-amber-900 shadow-2xs">
                <AlertTriangle size={20} className="shrink-0 text-amber-600 mt-0.5" />
                <div className="space-y-0.5">
                  <h3 className="font-semibold text-amber-900">
                    {t('mon_lease_warning_title')}
                  </h3>
                  <p className="text-xs text-amber-800 leading-relaxed">
                    {t('mon_lease_warning_desc')}
                  </p>
                </div>
              </div>
            )}

            {/* Highlight Stage Card & Action Callout (Expansive, Balanced, Edge-to-Edge) */}
            <section className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="p-6 sm:p-8 lg:p-10 space-y-6">

                {/* Top Status & Agent Metadata Row */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="inline-flex items-center gap-2 text-xs font-semibold text-zinc-800 bg-zinc-100 px-3.5 py-1 rounded-full border border-zinc-200">
                    <Activity size={14} className={snapshot.status === 'RUNNING' ? 'animate-pulse text-blue-600' : 'text-zinc-500'} />
                    <span>{t('mon_current_step')}</span>
                    <span className="text-zinc-400">•</span>
                    <span className="text-blue-700 font-bold uppercase tracking-wider text-[11px]">
                      {snapshot.status === 'RUNNING' ? (isEn ? 'Processing' : 'Đang xử lý') : statusLabel(snapshot.status, language)}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-700 font-medium">
                    <span className="rounded-lg bg-zinc-100 px-3 py-1 text-zinc-800 border border-zinc-200">
                      {t('mon_agent_assigned')}: <strong className="font-bold text-zinc-900">{current?.agent || (isEn ? 'Dispatcher' : 'Hệ thống')}</strong>
                    </span>
                    <span className="rounded-lg bg-zinc-100 px-3 py-1 text-zinc-800 border border-zinc-200">
                      {t('mon_iteration')}: <strong className="font-bold text-zinc-900">{snapshot.current_iteration}</strong>
                    </span>
                    <span className="rounded-lg bg-zinc-100 px-3 py-1 text-zinc-800 border border-zinc-200">
                      {t('mon_attempt')}: <strong className="font-bold text-zinc-900">#{snapshot.attempt_number}</strong>
                    </span>
                  </div>
                </div>

                {/* Stage Title & Expansive Description - TO TRÀN VIỀN, CHỮ ĐẬM TO HƠN */}
                <div className="space-y-3">
                  <h2 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-zinc-900 leading-tight">
                    {current
                      ? (isEn ? (current.name_en || current.name) : current.name)
                      : (snapshot.status === 'QUEUED'
                        ? (isEn ? 'Queued awaiting available worker' : 'Đang xếp hàng chờ worker nhận việc')
                        : (isEn ? 'Step not recorded yet' : 'Chưa ghi nhận bước xử lý'))}
                  </h2>

                  <p className="text-sm sm:text-base lg:text-lg text-zinc-700 font-medium leading-relaxed max-w-4xl">
                    {current
                      ? (isEn ? (current.description_en || current.description) : current.description)
                      : (isEn ? 'Execution steps will appear as soon as the pipeline starts running.' : 'Các bước thực tế sẽ xuất hiện ngay khi workflow bắt đầu ghi nhận tiến độ.')}
                  </p>
                </div>

                {/* Action Callout Banner - Spans Full Width ('to tràn viền') with Big, Clear Workspace Button */}
                <div className={`rounded-2xl p-5 sm:p-6 border transition-all ${
                  action.tone === 'amber'
                    ? 'border-amber-300 bg-amber-50/90 shadow-xs'
                    : action.tone === 'red'
                    ? 'border-red-300 bg-red-50/90 shadow-xs'
                    : action.tone === 'emerald'
                    ? 'border-emerald-300 bg-emerald-50/90 shadow-xs'
                    : 'border-zinc-200 bg-zinc-50/90 shadow-xs'
                }`}>
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
                    <div className="space-y-1.5 max-w-3xl">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${
                          action.tone === 'amber' ? 'bg-amber-600 animate-pulse' :
                          action.tone === 'red' ? 'bg-red-600' :
                          action.tone === 'emerald' ? 'bg-emerald-600' : 'bg-blue-600 animate-pulse'
                        }`} />
                        <h3 className="font-bold text-base sm:text-lg text-zinc-900">
                          {action.title}
                        </h3>
                      </div>
                      <p className="text-xs sm:text-sm text-zinc-700 leading-relaxed font-normal">
                        {action.text}
                      </p>
                    </div>

                    {/* NÚT MỞ WORKSPACE TO RÕ HƠN */}
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
                      <Link
                        href={
                          snapshot.status === 'WAITING_USER_DATA'
                            ? (snapshot.research_type === 'EMPIRICAL_COMPUTATIONAL' ? `/research/${id}?tab=experiments#upload-dataset` : `/research/${id}#fieldwork-section`)
                            : snapshot.status === 'WAITING_APPROVAL'
                            ? `/research/${id}#plan-review-section`
                            : (current?.key === 'CURATOR' || current?.key === 'RESEARCHER')
                            ? `/research/${id}?tab=sources`
                            : `/research/${id}`
                        }
                        className={`inline-flex items-center justify-center gap-2.5 rounded-xl px-6 py-3.5 text-sm sm:text-base font-bold transition-all shadow-sm hover:shadow-md active:scale-[0.99] cursor-pointer ${
                          action.tone === 'amber'
                            ? 'bg-amber-950 text-white hover:bg-black'
                            : action.tone === 'red'
                            ? 'bg-red-700 text-white hover:bg-red-800'
                            : action.tone === 'emerald'
                            ? 'bg-emerald-800 text-white hover:bg-emerald-900'
                            : 'bg-zinc-900 text-white hover:bg-zinc-800'
                        }`}
                      >
                        <FileText size={17} />
                        <span>{action.button}</span>
                        <ArrowUpRight size={17} className="shrink-0" />
                      </Link>

                      <span className="text-[11px] text-zinc-500 font-medium text-center sm:text-left">
                        {isEn ? 'Saved automatically' : 'Tự động lưu trữ'}
                      </span>
                    </div>
                  </div>
                </div>

              </div>

              {/* Research Workflow Pipeline (GitHub Actions style flow) */}
              <div className="border-t border-zinc-200 bg-zinc-50/50 p-5 sm:p-6">
                <PipelineFlow
                  stages={activeStages}
                  currentStep={snapshot.current_step}
                  activeStageKey={activeStageKey}
                  status={snapshot.status}
                  activities={snapshot.activities}
                  isEn={isEn}
                  t={t}
                  researchId={id}
                  researchType={snapshot.research_type}
                />
              </div>
            </section>

            {/* Saved Results Metric Cards */}
            <section aria-label="Artifacts" className="space-y-2.5">
              <div className="flex items-center justify-between px-1">
                <h2 className="text-sm sm:text-base font-semibold text-zinc-900 flex items-center gap-1.5">
                  <FileText size={16} className="text-zinc-600" />
                  <span>{t('mon_counts_title')}</span>
                </h2>
                <span className="text-xs text-zinc-500">
                  {t('mon_counts_desc')}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                {/* Metric 1: Sources */}
                <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs">
                  <div className="text-xs font-medium text-zinc-600 uppercase tracking-wider mb-1">
                    {t('mon_sources')}
                  </div>
                  <div className="text-2xl font-bold font-mono text-zinc-900">
                    {snapshot.counts.sources ?? 0}
                  </div>
                </div>

                {/* Metric 2: Verified Claims */}
                <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs">
                  <div className="text-xs font-medium text-zinc-600 uppercase tracking-wider mb-1">
                    {t('mon_claims')}
                  </div>
                  <div className="text-2xl font-bold font-mono text-zinc-900">
                    {snapshot.counts.verified_claims ?? 0}
                  </div>
                </div>

                {/* Metric 3: Report Versions */}
                <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs">
                  <div className="text-xs font-medium text-zinc-600 uppercase tracking-wider mb-1">
                    {t('mon_reports')}
                  </div>
                  <div className="text-2xl font-bold font-mono text-zinc-900">
                    {snapshot.counts.report_versions ?? 0}
                  </div>
                </div>

                {/* Metric 4: Artifacts */}
                <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs">
                  <div className="text-xs font-medium text-zinc-600 uppercase tracking-wider mb-1">
                    {t('mon_artifacts')}
                  </div>
                  <div className="text-2xl font-bold font-mono text-zinc-900">
                    {snapshot.counts.artifacts ?? 0}
                  </div>
                </div>

                {/* Metric 5: Experiments */}
                <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs col-span-2 sm:col-span-1">
                  <div className="text-xs font-medium text-zinc-600 uppercase tracking-wider mb-1">
                    {t('mon_experiments')}
                  </div>
                  <div className="text-2xl font-bold font-mono text-zinc-900">
                    {snapshot.counts.experiments ?? 0}
                  </div>
                </div>
              </div>

              {/* Warning on pending/failed sources */}
              {(snapshot.counts.pending_sources > 0 || snapshot.counts.failed_sources > 0) && (
                <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-900 shadow-2xs">
                  <AlertCircle size={16} className="shrink-0 text-amber-600 mt-0.5" />
                  <div>
                    {snapshot.counts.pending_sources > 0 && <span>{snapshot.counts.pending_sources} {isEn ? 'documents processing. ' : 'tài liệu đang xử lý. '}</span>}
                    {snapshot.counts.failed_sources > 0 && <span>{snapshot.counts.failed_sources} {isEn ? 'documents failed formatting. ' : 'tài liệu lỗi định dạng. '}</span>}
                    {isEn ? 'Only successfully indexed documents are verified as scientific evidence.' : 'Nguồn chưa hoàn tất xử lý sẽ chưa được tác tử Analyst đưa vào hệ thống bằng chứng khoa học.'}
                  </div>
                </div>
              )}
            </section>

            {/* Bottom 2-Column Section: Activity Log (2/3) + Resources Sidebar (1/3) */}
            <div className="grid items-start gap-5 lg:grid-cols-3">

              {/* Left Column: Activity Log Timeline (2/3 width) */}
              <section className="rounded-xl border border-zinc-200 bg-white shadow-2xs lg:col-span-2 overflow-hidden" aria-label="Activity Log">
                <div className="border-b border-zinc-200 bg-zinc-50/60 p-4 sm:p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="flex items-center gap-2 font-semibold text-sm sm:text-base text-zinc-900">
                      <Clock size={16} className="text-blue-600" />
                      <span>{t('mon_activity_log')}</span>
                    </h2>
                    <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-zinc-200 text-zinc-800">
                      {snapshot.activity_total}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-600 leading-relaxed">
                    {t('mon_activity_sub')}
                  </p>
                </div>

                {!snapshot.activities.length ? (
                  <div className="p-8 text-center text-xs sm:text-sm text-zinc-500 space-y-1">
                    <Clock size={24} className="mx-auto text-zinc-400 mb-2" />
                    <p>{t('mon_no_activities')}</p>
                  </div>
                ) : (
                  <ol className="divide-y divide-zinc-100">
                    {snapshot.activities.map((activity) => {
                      const stageMeta = activityStage(activity.agent);
                      return (
                        <li key={activity.id} className="p-4 sm:p-5 hover:bg-zinc-50/60 transition-colors">
                          <div className="flex items-start gap-3">
                            {/* Icon status indicator */}
                            <span className="mt-0.5 rounded-lg p-1.5 shrink-0 bg-zinc-100 text-zinc-700 border border-zinc-200">
                              {activity.status === 'SUCCESS' ? (
                                <CheckCircle2 size={15} className="text-emerald-600" />
                              ) : activity.status === 'FAILED' ? (
                                <AlertTriangle size={15} className="text-red-600" />
                              ) : (
                                <Circle size={15} className="text-blue-600 animate-pulse" />
                              )}
                            </span>

                            <div className="min-w-0 flex-1 space-y-1.5">
                              {/* Header row */}
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <h3 className="text-xs sm:text-sm font-semibold text-zinc-900">
                                    {stageMeta
                                      ? (isEn ? (stageMeta.name_en || stageMeta.name) : stageMeta.name)
                                      : (isEn ? 'System Operation' : 'Hoạt động hệ thống')}
                                  </h3>
                                  <span className="px-1.5 py-0.2 rounded text-[11px] font-medium bg-zinc-100 text-zinc-700 border border-zinc-200">
                                    {stageMeta?.agent || activity.agent}
                                  </span>
                                </div>
                                <StatusPill status={activity.status} />
                              </div>

                              {/* Metadata line */}
                              <p className="text-xs text-zinc-700 font-medium flex flex-wrap items-center gap-x-2 gap-y-0.5">
                                <span>{formatTime(activity.started_at, language)}</span>
                                <span>•</span>
                                <span>{Math.max(0, activity.duration_ms / 1000).toFixed(1)}s</span>
                                <span>•</span>
                                <span>{t('mon_iteration')} {activity.iteration}</span>
                              </p>

                              {/* Output summary badges */}
                              {activity.output && Object.keys(activity.output).length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pt-0.5">
                                  {Object.entries(activity.output).map(([key, value]) => {
                                    const strVal = String(value);
                                    const isVerdictPass = key === 'verdict' && ['PASS', 'PASSED'].includes(strVal);
                                    const isVerdictRevise = key === 'verdict' && ['REVISE', 'NEED_MORE_DATA', 'NEEDS_REVIEW'].includes(strVal);
                                    const isVerdictFail = key === 'verdict' && strVal === 'FAILED';

                                    const dotColor = isVerdictPass
                                      ? 'bg-emerald-600'
                                      : isVerdictRevise
                                      ? 'bg-amber-600'
                                      : isVerdictFail
                                      ? 'bg-red-600'
                                      : null;

                                    return (
                                      <span
                                        key={key}
                                        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-zinc-100/90 px-2 py-0.5 text-xs font-medium text-zinc-800"
                                      >
                                        {dotColor && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />}
                                        {outputLabel(key, value, language)}
                                      </span>
                                    );
                                  })}
                                </div>
                              )}

                              {/* Error callout if step logged error */}
                              {activity.has_error && (
                                <div className="rounded-md bg-red-50 border border-red-200 p-2 text-xs text-red-800 flex items-center gap-1.5">
                                  <AlertCircle size={13} className="shrink-0 text-red-600" />
                                  <span>{isEn ? 'This step reported an execution error. Technical logs are saved in system ledger.' : 'Bước này có ghi nhận lỗi nghiệp vụ. Chi tiết kỹ thuật được lưu trong log vận hành.'}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                )}

                {/* Pagination Controls */}
                <div className="flex items-center justify-between gap-3 border-t border-zinc-200 bg-zinc-50/60 p-3.5 text-xs text-zinc-600">
                  <button
                    type="button"
                    disabled={!offset}
                    onClick={() => setHistoryPage({ taskId: id, offset: Math.max(0, offset - 20) })}
                    className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 font-medium text-zinc-700 hover:bg-zinc-50 transition-colors disabled:opacity-40 disabled:pointer-events-none shadow-2xs"
                  >
                    <ChevronLeft size={13} /> {t('mon_newer')}
                  </button>

                  <span className="font-medium">
                    {snapshot.activities.length
                      ? `${offset + 1}–${offset + snapshot.activities.length} / ${snapshot.activity_total}`
                      : '0'}
                  </span>

                  <button
                    type="button"
                    disabled={offset + 20 >= snapshot.activity_total}
                    onClick={() => setHistoryPage({ taskId: id, offset: offset + 20 })}
                    className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 font-medium text-zinc-700 hover:bg-zinc-50 transition-colors disabled:opacity-40 disabled:pointer-events-none shadow-2xs"
                  >
                    {t('mon_older')} <ChevronRight size={13} />
                  </button>
                </div>
              </section>

              {/* Right Column: Resources & Milestones Sidebar (1/3 width) */}
              <aside className="space-y-4">

                {/* Card 1: Resource Ledger */}
                <section className="rounded-xl border border-zinc-200 bg-white p-4 sm:p-5 shadow-2xs" aria-label="Resources">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="font-semibold text-sm sm:text-base text-zinc-900">
                      {t('mon_cost_ledger')}
                    </h2>
                  </div>

                  <div className="p-3.5 rounded-lg bg-zinc-50 border border-zinc-200">
                    <div className="text-xs text-zinc-600">
                      {t('mon_cost_est')}
                    </div>
                    <div className="text-2xl font-bold font-mono text-zinc-900 mt-0.5">
                      ${snapshot.estimated_cost_usd.toFixed(4)}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">
                      {t('mon_cost_source')}: {snapshot.accounting_source === 'PROVIDER_LEDGER'
                        ? (isEn ? 'Provider settlement ledger' : 'Sổ đối soát API Provider')
                        : (isEn ? 'Agent estimates' : 'Lịch sử ước tính Agent')}
                    </div>
                  </div>

                  <dl className="mt-3 divide-y divide-zinc-100 text-xs">
                    <div className="flex justify-between py-2">
                      <dt className="text-zinc-600">{t('mon_cost_reserved')}</dt>
                      <dd className="font-mono font-medium text-zinc-900">${snapshot.reserved_cost_usd.toFixed(4)}</dd>
                    </div>
                    <div className="flex justify-between py-2">
                      <dt className="text-zinc-600">{t('mon_cost_tokens')}</dt>
                      <dd className="font-mono font-medium text-zinc-900">{snapshot.recorded_tokens.toLocaleString(isEn ? 'en-US' : 'vi-VN')}</dd>
                    </div>
                    <div className="flex justify-between py-2">
                      <dt className="text-zinc-600">{t('mon_experiments')}</dt>
                      <dd className="font-mono font-medium text-zinc-900">{snapshot.counts.experiments ?? 0}</dd>
                    </div>
                  </dl>

                  <p className="mt-2.5 text-[11px] text-zinc-500 leading-relaxed">
                    {t('mon_cost_disclaimer')}
                  </p>
                </section>

                {/* Card 2: System Milestones */}
                <section className="rounded-xl border border-zinc-200 bg-white p-4 sm:p-5 shadow-2xs" aria-label="Milestones">
                  <h2 className="font-semibold text-sm sm:text-base text-zinc-900 mb-3">
                    {t('mon_milestones')}
                  </h2>

                  <dl className="space-y-2 text-xs">
                    <div className="border-b border-zinc-100 pb-1.5">
                      <dt className="text-zinc-500">{isEn ? 'Created' : 'Khởi tạo bài'}</dt>
                      <dd className="text-zinc-800 font-medium">{formatTime(snapshot.created_at, language)}</dd>
                    </div>
                    <div className="border-b border-zinc-100 pb-1.5">
                      <dt className="text-zinc-500">{isEn ? 'Last status update' : 'Cập nhật trạng thái'}</dt>
                      <dd className="text-zinc-800 font-medium">{formatTime(snapshot.updated_at, language)}</dd>
                    </div>
                    <div className="border-b border-zinc-100 pb-1.5">
                      <dt className="text-zinc-500">{isEn ? 'Backend sample time' : 'Thời điểm lấy mẫu'}</dt>
                      <dd className="text-zinc-800 font-medium">{formatTime(snapshot.observed_at, language)}</dd>
                    </div>
                    <div>
                      <dt className="text-zinc-500">{isEn ? 'Completion time' : 'Kết thúc ghi nhận'}</dt>
                      <dd className="text-zinc-800 font-medium">{formatTime(snapshot.completed_at, language)}</dd>
                    </div>
                  </dl>
                </section>

                {/* Card 3: Quick Guidance */}
                <section className="rounded-xl border border-zinc-200 bg-white p-4 sm:p-5 shadow-2xs">
                  <h3 className="font-semibold text-xs text-zinc-900 uppercase tracking-wider mb-1.5">
                    {t('mon_parallel_title')}
                  </h3>
                  <p className="text-xs text-zinc-600 leading-relaxed font-normal">
                    {t('mon_parallel_desc')}
                  </p>
                  <div className="mt-3 pt-2.5 border-t border-zinc-100 flex flex-col gap-1.5">
                    <Link
                      href={`/research/${id}`}
                      className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 transition-colors shadow-2xs"
                    >
                      <span>{t('nav_workspace')}</span>
                      <ArrowUpRight size={13} />
                    </Link>
                    <Link
                      href="/research/monitor"
                      className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 transition-colors"
                    >
                      {t('nav_all_monitors')}
                    </Link>
                  </div>
                </section>

              </aside>
            </div>
          </>
        )}

      </div>
    </main>
  );
}
