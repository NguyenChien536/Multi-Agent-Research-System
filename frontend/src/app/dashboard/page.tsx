'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle, CheckCircle2, Clock, FileText,
  Play, Plus, RefreshCw, Search, Trash2, XCircle, ArrowUpRight,
  Activity, Filter, ChevronDown, ChevronUp, ExternalLink
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Components';
import { api } from '@/lib/api';
import { currentStage, statusLabel } from '@/lib/monitoring';
import { useLanguage } from '@/lib/i18n';
import type { ResearchTaskResponse, UserResponse } from '@/types';

const ACTIVE_STATUSES = new Set([
  'QUEUED', 'RUNNING', 'PLANNING', 'RESEARCHING', 'INDEXING',
  'ANALYZING', 'WRITING', 'REVIEWING', 'FINALIZING', 'RETRYING',
]);
const ATTENTION_STATUSES = new Set(['WAITING_APPROVAL', 'WAITING_USER_DATA', 'NEEDS_REVIEW', 'FAILED']);

function StatusBadge({ status }: { status: string }) {
  const { language, t } = useLanguage();

  const isActive = ACTIVE_STATUSES.has(status);
  const isAttention = ATTENTION_STATUSES.has(status);
  const isCompleted = status === 'COMPLETED' || status === 'SUCCESS';

  const dotColor = isCompleted
    ? 'bg-emerald-500'
    : status === 'QUEUED'
    ? 'bg-zinc-400 animate-pulse'
    : isActive
    ? 'bg-blue-500 animate-pulse'
    : status.startsWith('WAITING')
    ? 'bg-amber-500 animate-pulse'
    : status === 'FAILED'
    ? 'bg-red-500'
    : status === 'NEEDS_REVIEW'
    ? 'bg-orange-500'
    : 'bg-zinc-400';

  const containerCls = isCompleted
    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
    : status === 'QUEUED' || status === 'PLANNING'
    ? 'bg-zinc-100 border-zinc-200 text-zinc-700'
    : isActive
    ? 'bg-blue-50 border-blue-200 text-blue-800'
    : status.startsWith('WAITING')
    ? 'bg-amber-50 border-amber-200 text-amber-900'
    : status === 'FAILED'
    ? 'bg-red-50 border-red-200 text-red-800'
    : status === 'NEEDS_REVIEW'
    ? 'bg-orange-50 border-orange-200 text-orange-800'
    : 'bg-zinc-100 border-zinc-200 text-zinc-700';

  const label = status === 'COMPLETED'
    ? t('status_completed')
    : status === 'WAITING_APPROVAL'
    ? t('status_waiting_approval')
    : status === 'WAITING_USER_DATA'
    ? t('status_waiting_user_data')
    : status === 'FAILED'
    ? t('status_failed')
    : status === 'NEEDS_REVIEW'
    ? t('status_needs_review')
    : status === 'PENDING'
    ? t('status_pending')
    : status === 'CANCELLED'
    ? t('status_cancelled')
    : statusLabel(status, language);

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${containerCls}`}>
      <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
      <span>{label}</span>
    </span>
  );
}

function formatDate(value: string, lang: 'en' | 'vi') {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return lang === 'en' ? 'Unknown' : 'Không rõ';
  return new Intl.DateTimeFormat(lang === 'en' ? 'en-US' : 'vi-VN', {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(date);
}

function formatDuration(startedAt: string, completedAt: string | null | undefined, lang: 'en' | 'vi') {
  if (!completedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  const diffSec = Math.round((end - start) / 1000);
  if (diffSec < 60) return `${diffSec} ${lang === 'en' ? 'sec' : 'giây'}`;
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${mins % 60}m`;
}

function formatNumber(num: number, lang: 'en' | 'vi') {
  return num.toLocaleString(lang === 'en' ? 'en-US' : 'vi-VN');
}

export default function DashboardPage() {
  const router = useRouter();
  const { language, t } = useLanguage();

  const [tasks, setTasks] = useState<ResearchTaskResponse[]>([]);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'ATTENTION' | 'COMPLETED'>('ALL');
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'REVIEW' | 'EMPIRICAL_COMPUTATIONAL' | 'EMPIRICAL_HUMAN'>('ALL');
  const [depthFilter, setDepthFilter] = useState<'ALL' | 'SHALLOW' | 'STANDARD' | 'DEEP'>('ALL');
  const [showResourceTable, setShowResourceTable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setTasks(await api.tasks.list(0, 100));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load research tasks.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
    api.auth.me().then(setUser).catch(() => {});
  }, [loadTasks]);

  const handleStartTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActionLoadingId(id);
    setActionError('');
    try {
      await api.tasks.start(id);
      await loadTasks();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t('start_error'));
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCancelTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t('confirm_stop'))) return;
    setActionLoadingId(id);
    setActionError('');
    try {
      await api.tasks.cancel(id);
      await loadTasks();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t('stop_error'));
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDeleteTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t('confirm_delete'))) return;
    setActionLoadingId(id);
    setActionError('');
    try {
      await api.tasks.delete(id);
      await loadTasks();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t('delete_error'));
    } finally {
      setActionLoadingId(null);
    }
  };

  const filtered = useMemo(() => {
    return tasks.filter(task => {
      const matchQuery = `${task.title} ${task.research_question}`.toLowerCase().includes(query.trim().toLowerCase());
      if (!matchQuery) return false;
      if (statusFilter === 'ACTIVE' && !ACTIVE_STATUSES.has(task.status)) return false;
      if (statusFilter === 'ATTENTION' && !ATTENTION_STATUSES.has(task.status)) return false;
      if (statusFilter === 'COMPLETED' && task.status !== 'COMPLETED') return false;

      if (typeFilter !== 'ALL' && (task.research_type || 'REVIEW') !== typeFilter) return false;
      if (depthFilter !== 'ALL' && task.research_depth !== depthFilter) return false;

      return true;
    });
  }, [tasks, query, statusFilter, typeFilter, depthFilter]);

  // Overall Statistics
  const totalTasks = tasks.length;
  const activeCount = tasks.filter(task => ACTIVE_STATUSES.has(task.status)).length;
  const attentionCount = tasks.filter(task => ATTENTION_STATUSES.has(task.status)).length;
  const completedCount = tasks.filter(task => task.status === 'COMPLETED').length;
  const completionRate = totalTasks > 0 ? Math.round((completedCount / totalTasks) * 100) : 0;

  const totalCostUSD = tasks.reduce((sum, t) => sum + (Number(t.total_cost_usd) || 0), 0);
  const totalTokensUsed = tasks.reduce((sum, t) => sum + (Number(t.total_tokens_used) || 0), 0);
  const avgCostPerTask = totalTasks > 0 ? totalCostUSD / totalTasks : 0;
  const avgTokensPerTask = totalTasks > 0 ? Math.round(totalTokensUsed / totalTasks) : 0;

  // Breakdown by Research Methodology
  const methodAnalytics = useMemo(() => {
    const list = [
      {
        type: 'REVIEW' as const,
        name: t('method_review_name'),
        badge: 'REVIEW',
        desc: t('method_review_desc'),
        color: 'text-zinc-800',
        bg: 'bg-zinc-100',
        border: 'border-zinc-200',
        barColor: 'bg-zinc-700',
      },
      {
        type: 'EMPIRICAL_COMPUTATIONAL' as const,
        name: t('method_comp_name'),
        badge: 'COMPUTATIONAL',
        desc: t('method_comp_desc'),
        color: 'text-zinc-800',
        bg: 'bg-zinc-100',
        border: 'border-zinc-200',
        barColor: 'bg-zinc-700',
      },
      {
        type: 'EMPIRICAL_HUMAN' as const,
        name: t('method_human_name'),
        badge: 'FIELDWORK',
        desc: t('method_human_desc'),
        color: 'text-zinc-800',
        bg: 'bg-zinc-100',
        border: 'border-zinc-200',
        barColor: 'bg-zinc-700',
      },
    ];

    return list.map(item => {
      const typeTasks = tasks.filter(task => (task.research_type || 'REVIEW') === item.type);
      const count = typeTasks.length;
      const countPct = totalTasks > 0 ? Math.round((count / totalTasks) * 100) : 0;
      const tokens = typeTasks.reduce((acc, t) => acc + (Number(t.total_tokens_used) || 0), 0);
      const tokensPct = totalTokensUsed > 0 ? Math.round((tokens / totalTokensUsed) * 100) : 0;
      const cost = typeTasks.reduce((acc, t) => acc + (Number(t.total_cost_usd) || 0), 0);
      const costPct = totalCostUSD > 0 ? Math.round((cost / totalCostUSD) * 100) : 0;
      const avgCost = count > 0 ? cost / count : 0;
      const completed = typeTasks.filter(t => t.status === 'COMPLETED').length;
      const active = typeTasks.filter(t => ACTIVE_STATUSES.has(t.status)).length;
      const attention = typeTasks.filter(t => ATTENTION_STATUSES.has(t.status)).length;

      return {
        ...item,
        count,
        countPct,
        tokens,
        tokensPct,
        cost,
        costPct,
        avgCost,
        completed,
        active,
        attention,
      };
    });
  }, [tasks, totalTasks, totalTokensUsed, totalCostUSD, t]);

  return (
    <main className="flex-1 h-full w-full overflow-y-auto bg-white p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-[1720px] mx-auto space-y-6">

        {/* Main Dashboard Header */}
        <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white p-5 sm:p-6 rounded-xl border border-zinc-200 shadow-2xs">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-zinc-100 text-zinc-700 tracking-wider uppercase">
                {t('dash_badge')}
              </span>
              <span className="text-zinc-300">•</span>
              <span className="text-xs text-zinc-600 font-medium">
                {t('dash_subtitle')}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
              {t('dash_title')}
            </h1>
            <p className="text-zinc-600 text-xs sm:text-sm font-normal mt-0.5 leading-relaxed max-w-3xl">
              {t('dash_desc')}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 shrink-0">
            <Button
              variant="outline"
              onClick={() => void loadTasks()}
              disabled={loading}
              aria-label={t('dash_btn_refresh')}
              className="h-9 px-3 border-zinc-200 text-zinc-700 hover:text-zinc-900 hover:bg-zinc-50 text-xs font-medium"
            >
              <RefreshCw size={13} className={`mr-1.5 ${loading ? 'animate-spin text-blue-600' : 'text-zinc-500'}`} />
              {t('dash_btn_refresh')}
            </Button>

            <Link
              href="/research/monitor"
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 transition-colors shadow-2xs"
            >
              <Activity size={14} className="text-blue-600" />
              <span>{t('dash_btn_monitor')}</span>
            </Link>

            <Link
              href="/"
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-3.5 text-xs font-medium text-white hover:bg-zinc-800 transition-colors shadow-2xs"
            >
              <Plus size={14} />
              <span>{t('dash_btn_new')}</span>
            </Link>
          </div>
        </header>

        {/* Top Key Metrics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

          {/* Card 1: Total Tasks */}
          <div className="p-5 rounded-2xl bg-white border border-stone-200/90 shadow-xs">
            <div className="flex items-center justify-between text-zinc-600 mb-1.5">
              <span className="text-xs font-medium text-zinc-600 uppercase tracking-wider">
                {t('kpi_total_tasks')}
              </span>
              <FileText size={16} className="text-zinc-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-zinc-900">
              {totalTasks}
            </div>
            <div className="mt-2.5 pt-2.5 border-t border-stone-100 flex items-center justify-between text-xs text-zinc-600">
              <span>{t('kpi_completion_rate')}:</span>
              <strong className="font-semibold text-emerald-700">
                {completionRate}% ({completedCount}/{totalTasks})
              </strong>
            </div>
          </div>

          {/* Card 2: Active Pipeline */}
          <div className="p-5 rounded-2xl bg-white border border-stone-200/90 shadow-xs">
            <div className="flex items-center justify-between text-zinc-600 mb-1.5">
              <span className="text-xs font-medium text-blue-700 uppercase tracking-wider">
                {t('kpi_in_progress')}
              </span>
              <Activity size={16} className="text-blue-600" />
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-blue-700">
              {activeCount}
            </div>
            <div className="mt-2.5 pt-2.5 border-t border-stone-100 flex items-center justify-between text-xs text-zinc-600">
              <span>{t('kpi_needs_attention')}:</span>
              <strong className="font-semibold text-amber-700">
                {attentionCount}
              </strong>
            </div>
          </div>

          {/* Card 3: Total Tokens */}
          <div className="p-5 rounded-2xl bg-white border border-stone-200/90 shadow-xs">
            <div className="flex items-center justify-between text-zinc-600 mb-1.5">
              <span className="text-xs font-medium text-zinc-600 uppercase tracking-wider">
                {t('kpi_tokens_used')}
              </span>
              <span className="text-xs text-zinc-500 font-mono">tokens</span>
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-zinc-900">
              {formatNumber(totalTokensUsed, language)}
            </div>
            <div className="mt-2.5 pt-2.5 border-t border-stone-100 flex items-center justify-between text-xs text-zinc-600">
              <span>{t('kpi_avg_tokens')}:</span>
              <span className="font-mono text-zinc-800 font-medium">
                ~{formatNumber(avgTokensPerTask, language)}
              </span>
            </div>
          </div>

          {/* Card 4: Total Cost (USD) */}
          <div className="p-5 rounded-2xl bg-white border border-stone-200/90 shadow-xs">
            <div className="flex items-center justify-between text-zinc-600 mb-1.5">
              <span className="text-xs font-medium text-zinc-600 uppercase tracking-wider">
                {t('kpi_total_cost')}
              </span>
              <span className="text-xs text-zinc-500 font-mono">USD</span>
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-emerald-700">
              ${totalCostUSD.toFixed(4)}
            </div>
            <div className="mt-2.5 pt-2.5 border-t border-stone-100 flex items-center justify-between text-xs text-zinc-600">
              <span>{t('kpi_avg_cost')}:</span>
              <span className="font-mono text-zinc-800 font-medium">
                ${avgCostPerTask.toFixed(4)}
              </span>
            </div>
          </div>

        </div>

        {/* Main Research Tasks List & Controls */}
        {actionError && <div role="alert" className="sticky top-0 z-20 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <span>{actionError}</span><button type="button" onClick={()=>setActionError('')} aria-label={language==='en'?'Dismiss error':'Đóng thông báo lỗi'}><XCircle size={18} /></button>
        </div>}
        <section className="bg-white rounded-2xl border border-stone-200/90 shadow-xs overflow-hidden" aria-label="Tasks List">

          {/* Filter Bar & Controls */}
          <div className="p-5 border-b border-stone-200/80 bg-white space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-base text-zinc-900 flex items-center gap-2">
                  <span>{t('tasks_list_title')}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-800 font-medium">
                    {filtered.length} / {totalTasks}
                  </span>
                </h2>
                <p className="text-xs text-zinc-600 mt-0.5">
                  {t('tasks_list_desc')}
                </p>
              </div>

              {/* Search input */}
              <div className="relative w-full sm:w-80">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  type="search"
                  placeholder={t('search_placeholder')}
                  aria-label="Search"
                  className="w-full pl-9 pr-3 py-1.5 bg-white border border-zinc-200 rounded-lg text-xs font-normal text-zinc-900 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-900 transition-all shadow-2xs"
                />
              </div>
            </div>

            {/* Filter Pills Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2.5 pt-2 border-t border-zinc-200/60 text-xs">

              {/* Status Filter Tabs */}
              <div className="flex flex-wrap items-center gap-1">
                <span className="text-zinc-600 mr-1 flex items-center gap-1 font-medium">
                  <Filter size={12} className="text-zinc-500" /> {t('filter_status_label')}
                </span>

                {[
                  { id: 'ALL', label: t('filter_all'), count: totalTasks },
                  { id: 'ACTIVE', label: t('filter_active'), count: activeCount },
                  { id: 'ATTENTION', label: t('filter_attention'), count: attentionCount },
                  { id: 'COMPLETED', label: t('filter_completed'), count: completedCount },
                ].map(tab => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setStatusFilter(tab.id as any)}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                      statusFilter === tab.id
                        ? 'bg-zinc-900 text-white'
                        : 'bg-white text-zinc-700 hover:bg-zinc-100 border border-zinc-200'
                    }`}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>

              {/* Method and Depth Selectors */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-zinc-600 font-medium">{t('filter_type_label')}</span>
                  <select
                    value={typeFilter}
                    onChange={e => setTypeFilter(e.target.value as any)}
                    className="bg-white border border-zinc-200 rounded-md px-2 py-1 text-xs text-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-900"
                  >
                    <option value="ALL">{t('filter_type_all')}</option>
                    <option value="REVIEW">{t('method_review_name')}</option>
                    <option value="EMPIRICAL_COMPUTATIONAL">{t('method_comp_name')}</option>
                    <option value="EMPIRICAL_HUMAN">{t('method_human_name')}</option>
                  </select>
                </div>

                <div className="flex items-center gap-1">
                  <span className="text-zinc-600 font-medium">{t('filter_depth_label')}</span>
                  <select
                    value={depthFilter}
                    onChange={e => setDepthFilter(e.target.value as any)}
                    className="bg-white border border-zinc-200 rounded-md px-2 py-1 text-xs text-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-900"
                  >
                    <option value="ALL">{t('filter_depth_all')}</option>
                    <option value="SHALLOW">{t('filter_depth_shallow')}</option>
                    <option value="STANDARD">{t('filter_depth_standard')}</option>
                    <option value="DEEP">{t('filter_depth_deep')}</option>
                  </select>
                </div>

                {(statusFilter !== 'ALL' || typeFilter !== 'ALL' || depthFilter !== 'ALL' || query) && (
                  <button
                    type="button"
                    onClick={() => {
                      setStatusFilter('ALL');
                      setTypeFilter('ALL');
                      setDepthFilter('ALL');
                      setQuery('');
                    }}
                    className="text-xs text-blue-600 hover:text-blue-800 underline ml-1 cursor-pointer font-medium"
                  >
                    {t('reset_filters')}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div role="alert" className="p-4 text-xs font-medium text-red-700 bg-red-50 border-b border-red-200 flex items-center justify-between">
              <span>{error}</span>
              <button className="underline font-semibold" onClick={() => void loadTasks()}>
                {t('dash_btn_refresh')}
              </button>
            </div>
          )}

          {/* Table Content */}
          {loading ? (
            <div className="p-12 text-center text-zinc-600">
              <RefreshCw size={24} className="mx-auto animate-spin mb-2 text-blue-600" />
              <p className="text-xs sm:text-sm font-medium">Loading research tasks...</p>
            </div>
          ) : !error && filtered.length === 0 ? (
            <div className="p-12 text-center text-zinc-600 space-y-2">
              <FileText size={32} className="mx-auto text-zinc-400" />
              <p className="font-semibold text-sm text-zinc-900">
                {query || statusFilter !== 'ALL' || typeFilter !== 'ALL' || depthFilter !== 'ALL'
                  ? t('empty_filtered_title')
                  : t('empty_workspace_title')}
              </p>
              <p className="text-xs text-zinc-600 max-w-sm mx-auto">
                {t('empty_workspace_desc')}
              </p>
              <div className="pt-2">
                <Link
                  href="/"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 text-white font-medium text-xs hover:bg-zinc-800 transition-colors shadow-2xs"
                >
                  <Plus size={14} /> {t('btn_create_first')}
                </Link>
              </div>
            </div>
          ) : !error && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs sm:text-sm">
                <thead>
                  <tr className="bg-zinc-50 border-b border-zinc-200 text-xs font-semibold text-zinc-700">
                    <th className="py-3 px-5 min-w-[320px]">{t('th_title')}</th>
                    <th className="py-3 px-5 min-w-[180px]">{t('th_method')}</th>
                    <th className="py-3 px-5 min-w-[190px]">{t('th_status')}</th>
                    <th className="py-3 px-5 min-w-[150px]">{t('th_cost')}</th>
                    <th className="py-3 px-5 min-w-[140px]">{t('th_updated')}</th>
                    <th className="py-3 px-5 text-right min-w-[160px]">{t('th_actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {filtered.map(task => {
                    const isTaskWorking = ACTIVE_STATUSES.has(task.status);
                    const isQueued = task.status === 'QUEUED';
                    const isPlanning = task.status === 'PLANNING';
                    const needsAttention = ATTENTION_STATUSES.has(task.status);
                    const stage = currentStage(task.current_step);
                    const duration = formatDuration(task.created_at, task.completed_at, language);
                    const isFieldwork = task.research_type === 'EMPIRICAL_HUMAN';
                    const isComputational = task.research_type === 'EMPIRICAL_COMPUTATIONAL';

                    return (
                      <tr
                        key={task.id}
                        onClick={() => router.push(`/research/${task.id}`)}
                        className={`hover:bg-zinc-50/80 transition-colors cursor-pointer group ${
                          needsAttention ? 'bg-amber-50/30' : isTaskWorking ? 'bg-blue-50/20' : ''
                        }`}
                      >
                        {/* 1. Title & Question */}
                        <td className="py-3.5 px-5">
                          <div className="flex items-start gap-3">
                            <span className={`mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors border text-zinc-700 ${
                              isTaskWorking ? 'bg-blue-50 border-blue-200 text-blue-700 group-hover:bg-blue-100'
                              : needsAttention ? 'bg-amber-50 border-amber-200 text-amber-700'
                              : 'bg-zinc-100 border-zinc-200 group-hover:bg-zinc-200'
                            }`}>
                              <FileText size={15} />
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="font-semibold text-sm text-zinc-900 group-hover:text-blue-700 transition-colors line-clamp-1">
                                {task.title}
                              </div>
                              <div className="text-xs text-zinc-600 font-normal line-clamp-1 mt-0.5">
                                {task.research_question}
                              </div>
                              <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500 font-normal">
                                <span className="font-mono">#{task.id.slice(0, 8)}</span>
                                <span className="text-zinc-300">•</span>
                                <span>{formatDate(task.created_at, language)}</span>
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* 2. Methodology & Style */}
                        <td className="py-3.5 px-5">
                          <div className="flex flex-col gap-1 items-start">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium text-zinc-800 bg-zinc-100 border border-zinc-200">
                              {isComputational
                                ? (language === 'en' ? 'Computational' : 'Thực nghiệm tính toán')
                                : isFieldwork
                                ? (language === 'en' ? 'Fieldwork' : 'Thực nghiệm thực địa')
                                : (language === 'en' ? 'Literature Review' : 'Tổng quan tài liệu')}
                            </span>

                            <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-600 mt-0.5">
                              <span>
                                {task.research_depth === 'DEEP'
                                  ? (language === 'en' ? 'Deep' : 'Chuyên sâu')
                                  : task.research_depth === 'STANDARD'
                                  ? (language === 'en' ? 'Standard' : 'Tiêu chuẩn')
                                  : (language === 'en' ? 'Fast' : 'Nhanh')}
                              </span>
                              <span className="text-zinc-400">•</span>
                              <span>{task.citation_style || 'IEEE'}</span>
                            </div>
                          </div>
                        </td>

                        {/* 3. Status & Current Step */}
                        <td className="py-3.5 px-5">
                          <div className="flex flex-col gap-1.5 items-start">
                            <StatusBadge status={task.status} />
                            {/* Active pipeline: show animated step indicator */}
                            {(isTaskWorking || isQueued || isPlanning) && (
                              <div className="flex items-center gap-1.5 text-xs font-medium text-blue-700">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse shrink-0" />
                                <span className="text-xs">
                                  {isQueued
                                    ? (language === 'en' ? 'Waiting in queue…' : 'Đang chờ chạy…')
                                    : isPlanning
                                    ? (language === 'en' ? 'AI agents initializing…' : 'Agents đang khởi động…')
                                    : stage
                                    ? (language === 'en' ? (stage.name_en || stage.name) : stage.name)
                                    : task.current_step || ''}
                                </span>
                                {task.max_iterations > 1 && (
                                  <span className="text-zinc-500 font-medium">
                                    ({task.current_iteration}/{task.max_iterations})
                                  </span>
                                )}
                              </div>
                            )}
                            {/* Attention statuses: show what to do */}
                            {needsAttention && (
                              <div className="text-xs text-amber-700 font-medium flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                                {task.status === 'WAITING_APPROVAL'
                                  ? (language === 'en' ? 'Plan awaiting your approval' : 'Kế hoạch chờ phê duyệt')
                                  : task.status === 'WAITING_USER_DATA'
                                  ? (language === 'en' ? 'Awaiting field data upload' : 'Chờ tải lên dữ liệu')
                                  : task.status === 'FAILED'
                                  ? (language === 'en' ? 'Research failed — review logs' : 'Lỗi — xem nhật ký')
                                  : (language === 'en' ? 'Needs review' : 'Cần xem xét')}
                              </div>
                            )}
                            {/* Idle tasks */}
                            {!isTaskWorking && !needsAttention && !isQueued && !isPlanning && stage && (
                              <div className="text-xs text-zinc-600 font-medium">
                                {language === 'en' ? (stage.name_en || stage.name) : stage.name}
                              </div>
                            )}
                          </div>
                        </td>

                        {/* 4. Cost & Tokens */}
                        <td className="py-3.5 px-5 whitespace-nowrap text-xs">
                          <div className="font-bold text-sm text-zinc-900 font-mono">
                            ${Number(task.total_cost_usd || 0).toFixed(4)}
                          </div>
                          <div className="text-xs text-zinc-600 font-medium mt-0.5">
                            {formatNumber(task.total_tokens_used || 0, language)} tokens
                          </div>
                        </td>

                        {/* 5. Updated Time & Duration */}
                        <td className="py-3.5 px-5 text-xs text-zinc-700 whitespace-nowrap">
                          <div className="font-medium text-zinc-800">{formatDate(task.updated_at, language)}</div>
                          {duration && (
                            <div className="text-xs text-zinc-500 mt-0.5 flex items-center gap-1 font-normal">
                              <Clock size={11} className="text-zinc-400" /> {duration}
                            </div>
                          )}
                        </td>

                        {/* 6. Quick Actions */}
                        <td className="py-3.5 px-5 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>

                                                        {/* Contextual Primary Action Button */}
                            {task.status === 'WAITING_APPROVAL' ? (
                              <Link
                                href={`/research/${task.id}`}
                                onClick={e => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500 text-white hover:bg-amber-600 transition-colors shadow-2xs mr-1"
                                title={language === 'en' ? 'Review & Approve Research Plan' : 'Xem và phê duyệt kế hoạch nghiên cứu'}
                              >
                                <span>{language === 'en' ? 'Review Plan' : 'Duyệt kế hoạch'}</span>
                                <ArrowUpRight size={13} />
                              </Link>
                            ) : task.status === 'WAITING_USER_DATA' ? (
                              <Link
                                href={`/research/${task.id}`}
                                onClick={e => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500 text-white hover:bg-amber-600 transition-colors shadow-2xs mr-1"
                                title={language === 'en' ? 'Upload Fieldwork Dataset' : 'Nạp dữ liệu thực địa'}
                              >
                                <span>{language === 'en' ? 'Upload Data' : 'Nạp dữ liệu'}</span>
                                <ArrowUpRight size={13} />
                              </Link>
                            ) : task.status === 'COMPLETED' ? (
                              <Link
                                href={`/research/${task.id}`}
                                onClick={e => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-zinc-900 text-white hover:bg-zinc-800 transition-colors shadow-2xs mr-1"
                                title={language === 'en' ? 'Read Final Paper' : 'Đọc bài báo hoàn chỉnh'}
                              >
                                <span>{language === 'en' ? 'Read Paper' : 'Đọc bài báo'}</span>
                                <ArrowUpRight size={13} />
                              </Link>
                            ) : (isTaskWorking || isQueued || isPlanning) ? (
                              <Link
                                href={`/research/${task.id}/monitor`}
                                onClick={e => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors shadow-2xs mr-1"
                                title={language === 'en' ? 'View Live Agent Progress' : 'Xem tiến độ các agent'}
                              >
                                <span>{language === 'en' ? 'Monitor' : 'Xem tiến độ'}</span>
                                <Activity size={13} />
                              </Link>
                            ) : null}

{/* Start / Rerun */}
                            {(task.status === 'PENDING' || task.status === 'CANCELLED') && (
                              <button
                                type="button"
                                onClick={(e) => void handleStartTask(task.id, e)}
                                disabled={actionLoadingId === task.id}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors cursor-pointer"
                                title={task.status === 'CANCELLED' ? t('btn_rerun') : t('btn_start')}
                              >
                                <Play size={11} />
                                <span>{task.status === 'CANCELLED' ? t('btn_rerun') : t('btn_start')}</span>
                              </button>
                            )}

                            {/* Cancel */}
                            {isTaskWorking && (
                              <button
                                type="button"
                                onClick={(e) => void handleCancelTask(task.id, e)}
                                disabled={actionLoadingId === task.id}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 transition-colors cursor-pointer"
                                title={t('btn_stop')}
                              >
                                <XCircle size={11} />
                                <span>{t('btn_stop')}</span>
                              </button>
                            )}

                            {/* Live Monitor */}
                            <Link
                              href={`/research/${task.id}/monitor`}
                              onClick={e => e.stopPropagation()}
                              className="p-1.5 rounded text-zinc-500 hover:text-blue-700 hover:bg-blue-50 transition-colors"
                              title={t('btn_view_monitor')}
                            >
                              <Activity size={15} />
                            </Link>

                            {/* Workspace */}
                            <Link
                              href={`/research/${task.id}`}
                              onClick={e => e.stopPropagation()}
                              className="p-1.5 rounded text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 transition-colors"
                              title={t('btn_open_workspace')}
                            >
                              <ArrowUpRight size={15} />
                            </Link>

                            {/* Delete */}
                            {(task.status === 'COMPLETED' || task.status === 'CANCELLED' || task.status === 'FAILED') && (
                              <button
                                type="button"
                                onClick={(e) => void handleDeleteTask(task.id, e)}
                                disabled={actionLoadingId === task.id}
                                className="p-1.5 rounded text-zinc-400 hover:text-red-700 hover:bg-red-50 transition-colors cursor-pointer"
                                title={t('btn_delete')}
                              >
                                <Trash2 size={14} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Methodology Analytics Table */}
        <section className="bg-white rounded-xl border border-zinc-200 shadow-2xs overflow-hidden">
          <div className="px-5 py-3.5 border-b border-zinc-200 flex items-center justify-between bg-zinc-50/70">
            <div>
              <h2 className="font-semibold text-sm sm:text-base text-zinc-900">
                {t('method_table_title')}
              </h2>
              <p className="text-xs text-zinc-600 mt-0.5">
                {t('method_table_desc')}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowResourceTable(!showResourceTable)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-zinc-200 bg-white text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              {showResourceTable ? (
                <>
                  <ChevronUp size={14} /> <span>{t('method_table_collapse')}</span>
                </>
              ) : (
                <>
                  <ChevronDown size={14} /> <span>{t('method_table_expand')}</span>
                </>
              )}
            </button>
          </div>

          {showResourceTable && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 p-5">
              {methodAnalytics.map(item => {
                const isSelected = typeFilter === item.type;
                return (
                  <div
                    key={item.type}
                    className={`rounded-2xl border p-5 transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'border-blue-400 bg-blue-50/50 shadow-md ring-2 ring-blue-200'
                        : 'border-zinc-200 bg-white hover:border-zinc-300 hover:shadow-xs'
                    }`}
                  >
                    <div>
                      {/* Method Header */}
                      <div className="flex items-start justify-between gap-3 mb-4">
                        <div>
                          <div className="font-bold text-base text-zinc-900 tracking-tight">{item.name}</div>
                          <div className="text-xs text-zinc-600 font-normal mt-0.5 line-clamp-1">{item.desc}</div>
                        </div>
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-zinc-100 text-zinc-800 border border-zinc-200 shrink-0">
                          {item.badge}
                        </span>
                      </div>

                      {/* Prominent High-Visibility Metrics */}
                      <div className="grid grid-cols-3 gap-2.5 bg-zinc-50/80 p-3.5 rounded-xl border border-zinc-200/90 mb-4">
                        {/* 1. Projects Count */}
                        <div className="text-center">
                          <div className="text-xs font-semibold uppercase text-zinc-600 tracking-wider mb-1">
                            {t('method_col_count')}
                          </div>
                          <div className="text-2xl sm:text-3xl font-extrabold text-zinc-950 font-mono leading-none">
                            {item.count}
                          </div>
                          <div className="text-xs font-mono font-medium text-zinc-600 mt-1">
                            {item.countPct}% {language === 'en' ? 'of total' : 'tổng'}
                          </div>
                        </div>

                        {/* 2. Tokens */}
                        <div className="text-center border-x border-zinc-200 px-1">
                          <div className="text-xs font-semibold uppercase text-blue-700 tracking-wider mb-1">
                            Tokens
                          </div>
                          <div className="text-2xl sm:text-3xl font-extrabold text-blue-800 font-mono leading-none">
                            {item.tokens >= 1000000
                              ? `${(item.tokens / 1000000).toFixed(1)}M`
                              : item.tokens >= 1000
                              ? `${(item.tokens / 1000).toFixed(0)}K`
                              : item.tokens}
                          </div>
                          <div className="text-xs font-mono font-medium text-blue-700 mt-1">
                            {item.tokensPct}% {language === 'en' ? 'volume' : 'lượng'}
                          </div>
                        </div>

                        {/* 3. Cost USD */}
                        <div className="text-center">
                          <div className="text-xs font-semibold uppercase text-emerald-700 tracking-wider mb-1">
                            Cost (USD)
                          </div>
                          <div className="text-2xl sm:text-3xl font-extrabold text-emerald-800 font-mono leading-none">
                            ${item.cost < 0.01 ? item.cost.toFixed(4) : item.cost.toFixed(3)}
                          </div>
                          <div className="text-xs font-mono font-medium text-emerald-700 mt-1">
                            {item.costPct}% {language === 'en' ? 'spend' : 'chi phí'}
                          </div>
                        </div>
                      </div>

                      {/* Average breakdown row */}
                      <div className="flex items-center justify-between text-xs text-zinc-700 px-1 mb-4 font-medium">
                        <span>{language === 'en' ? 'Avg. per task:' : 'TB mỗi bài:'}</span>
                        <span className="font-mono text-zinc-900 font-semibold">
                          ${item.avgCost.toFixed(4)} • ~{item.count > 0 ? Math.round(item.tokens / item.count).toLocaleString() : 0} tokens
                        </span>
                      </div>
                    </div>

                    {/* Status & Filter Toggle Action Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs border-t border-stone-100 pt-3 mt-1">
                      <div className="flex items-center gap-2.5">
                        <span className="inline-flex items-center gap-1 font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                          {item.completed} {language === 'en' ? 'done' : 'xong'}
                        </span>
                        {item.active > 0 && (
                          <span className="inline-flex items-center gap-1 font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                            {item.active} {language === 'en' ? 'active' : 'chạy'}
                          </span>
                        )}
                        {item.attention > 0 && (
                          <span className="inline-flex items-center gap-1 font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                            {item.attention} {language === 'en' ? 'action' : 'chờ'}
                          </span>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => setTypeFilter(isSelected ? 'ALL' : item.type)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-zinc-900 text-white shadow-2xs'
                            : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200 border border-zinc-200'
                        }`}
                      >
                        {isSelected ? t('method_filter_active') : t('method_filter_btn')}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>


      </div>
    </main>
  );
}
