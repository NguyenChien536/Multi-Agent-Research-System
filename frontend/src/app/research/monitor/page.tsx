'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import {
  Activity, ArrowUpRight, Filter, Clock, FileText, Plus, Search,
  CheckCircle2, AlertTriangle, ArrowLeft, RefreshCw, X
} from 'lucide-react';
import { api } from '@/lib/api';
import { currentStage } from '@/lib/monitoring';
import { useMonitorPoll } from '@/lib/use-monitor-poll';
import { PollStatus, StatusPill, formatTime } from '@/components/monitoring/MonitorUI';
import { useLanguage } from '@/lib/i18n';

export default function MonitorOverview() {
  const { language, t } = useLanguage();
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'RUNNING' | 'WAITING' | 'ATTENTION' | 'COMPLETED'>('ALL');
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'REVIEW' | 'EMPIRICAL_COMPUTATIONAL' | 'EMPIRICAL_HUMAN'>('ALL');

  const load = useCallback((signal: AbortSignal) => api.tasks.list(page * 20, 21, signal), [page]);
  const { data, error, loading, lastSuccess, refresh } = useMonitorPoll(load, 5000);

  const tasks = data?.slice(0, 20) || [];
  const visible = tasks.filter(task =>
    `${task.title} ${task.research_question || ''}`.toLowerCase().includes(query.trim().toLowerCase())
  );

  const ACTIVE_STATUSES = new Set([
    'QUEUED', 'RUNNING', 'PLANNING', 'RESEARCHING', 'INDEXING',
    'ANALYZING', 'WRITING', 'REVIEWING', 'FINALIZING', 'RETRYING',
  ]);
  const running = tasks.filter(task => ACTIVE_STATUSES.has(task.status)).length;
  const waiting = tasks.filter(task => task.status.startsWith('WAITING')).length;
  const attention = tasks.filter(task => ['FAILED', 'NEEDS_REVIEW', 'PARTIAL'].includes(task.status)).length;
  const completed = tasks.filter(task => task.status === 'COMPLETED').length;

  return (
    <main className="h-full overflow-y-auto bg-zinc-50/60 p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-[1720px] mx-auto space-y-6">

        {/* Top Header Card */}
        <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white p-5 sm:p-6 rounded-xl border border-zinc-200 shadow-2xs">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
              {t('mon_page_title')}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 shrink-0">
            <Link
              href="/dashboard"
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 text-xs font-medium text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 transition-colors shadow-2xs"
            >
              <ArrowLeft size={13} /> {t('nav_dashboard')}
            </Link>

            <Link
              href="/"
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-3.5 text-xs font-medium text-white hover:bg-zinc-800 transition-all shadow-2xs"
            >
              <Plus size={14} /> {t('dash_btn_new')}
            </Link>
          </div>
        </header>

        {/* 4 Metric Status Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Running */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => setStatusFilter(statusFilter === 'RUNNING' ? 'ALL' : 'RUNNING')}
            onKeyDown={e => e.key === 'Enter' && setStatusFilter(statusFilter === 'RUNNING' ? 'ALL' : 'RUNNING')}
            className={`p-4 sm:p-5 rounded-xl border transition-all cursor-pointer shadow-2xs ${
              statusFilter === 'RUNNING' ? 'border-blue-600 ring-2 ring-blue-500/20 bg-blue-50/20' : 'border-zinc-200 bg-white hover:border-zinc-300'
            }`}>
            <div className="flex items-center justify-between text-zinc-600 mb-1">
              <span className="text-xs sm:text-sm font-semibold text-blue-800 uppercase tracking-wide">{t('mon_card_running')}</span>
              <Activity size={16} className="text-blue-600 animate-pulse" />
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-zinc-900 mt-0.5">{data ? running : '—'}</div>
            <div className="text-xs sm:text-sm font-medium text-zinc-600 mt-1">{t('mon_card_running_sub')}</div>
          </div>

          {/* Card 2: Waiting */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => setStatusFilter(statusFilter === 'WAITING' ? 'ALL' : 'WAITING')}
            onKeyDown={e => e.key === 'Enter' && setStatusFilter(statusFilter === 'WAITING' ? 'ALL' : 'WAITING')}
            className={`p-4 sm:p-5 rounded-xl border transition-all cursor-pointer shadow-2xs ${
              statusFilter === 'WAITING' ? 'border-amber-600 ring-2 ring-amber-500/20 bg-amber-50/20' : 'border-zinc-200 bg-white hover:border-zinc-300'
            }`}>
            <div className="flex items-center justify-between text-zinc-600 mb-1">
              <span className="text-xs sm:text-sm font-semibold text-amber-800 uppercase tracking-wide">{t('mon_card_waiting')}</span>
              <Clock size={16} className="text-amber-600" />
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-zinc-900 mt-0.5">{data ? waiting : '—'}</div>
            <div className="text-xs sm:text-sm font-medium text-zinc-600 mt-1">{t('mon_card_waiting_sub')}</div>
          </div>

          {/* Card 3: Attention */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => setStatusFilter(statusFilter === 'ATTENTION' ? 'ALL' : 'ATTENTION')}
            onKeyDown={e => e.key === 'Enter' && setStatusFilter(statusFilter === 'ATTENTION' ? 'ALL' : 'ATTENTION')}
            className={`p-4 sm:p-5 rounded-xl border transition-all cursor-pointer shadow-2xs ${
              statusFilter === 'ATTENTION' ? 'border-red-600 ring-2 ring-red-500/20 bg-red-50/20' : 'border-zinc-200 bg-white hover:border-zinc-300'
            }`}>
            <div className="flex items-center justify-between text-zinc-600 mb-1">
              <span className="text-xs sm:text-sm font-semibold text-red-800 uppercase tracking-wide">{t('mon_card_attention')}</span>
              <AlertTriangle size={16} className="text-red-600" />
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-zinc-900 mt-0.5">{data ? attention : '—'}</div>
            <div className="text-xs sm:text-sm font-medium text-zinc-600 mt-1">{t('mon_card_attention_sub')}</div>
          </div>

          {/* Card 4: Completed */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => setStatusFilter(statusFilter === 'COMPLETED' ? 'ALL' : 'COMPLETED')}
            onKeyDown={e => e.key === 'Enter' && setStatusFilter(statusFilter === 'COMPLETED' ? 'ALL' : 'COMPLETED')}
            className={`p-4 sm:p-5 rounded-xl border transition-all cursor-pointer shadow-2xs ${
              statusFilter === 'COMPLETED' ? 'border-emerald-600 ring-2 ring-emerald-500/20 bg-emerald-50/20' : 'border-zinc-200 bg-white hover:border-zinc-300'
            }`}>
            <div className="flex items-center justify-between text-zinc-600 mb-1">
              <span className="text-xs sm:text-sm font-semibold text-emerald-800 uppercase tracking-wide">{t('mon_card_completed')}</span>
              <CheckCircle2 size={16} className="text-emerald-600" />
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-zinc-900 mt-0.5">{data ? completed : '—'}</div>
            <div className="text-xs sm:text-sm font-medium text-zinc-600 mt-1">{t('mon_card_completed_sub')}</div>
          </div>
        </div>

        {/* Sync Status Banner */}
        <PollStatus error={error} lastSuccess={lastSuccess} refresh={refresh} />

        {/* Task Monitoring List Section */}
        <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xs" aria-label="Monitored Tasks">
          {/* Section Subheader & Search */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-200 bg-zinc-50/60 p-4 sm:p-5">
            <div>
              <h2 className="font-semibold text-sm sm:text-base text-zinc-900 flex items-center gap-2">
                <span>{t('mon_table_header')}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-800 font-medium">
                  {t('mon_page_info')} {page + 1}
                </span>
              </h2>
              <p className="text-xs text-zinc-600 mt-0.5">
                {t('mon_table_desc')}
              </p>
            </div>

            {/* In-page Title Search */}
            <div className="relative w-full sm:w-72">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                aria-label="Filter title"
                placeholder={t('mon_filter_inpage')}
                value={query}
                onChange={e => setQuery(e.target.value)}
                className="w-full pl-9 pr-8 py-1.5 bg-white border border-zinc-200 rounded-lg text-xs font-normal text-zinc-900 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-900 transition-all shadow-2xs"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Loading Indicator */}
          {loading && !data && (
            <div role="status" className="p-12 text-center text-zinc-600">
              <RefreshCw size={24} className="mx-auto animate-spin mb-2 text-blue-600" />
              <p className="font-medium text-xs sm:text-sm">Loading monitoring data...</p>
            </div>
          )}

          {/* Empty Result */}
          {!loading && data && visible.length === 0 && (
            <div className="p-12 text-center text-zinc-600 space-y-2">
              <FileText size={32} className="mx-auto text-zinc-400 mb-1" />
              <p className="font-medium text-sm text-zinc-900">
                {tasks.length ? t('empty_filtered_title') : t('empty_workspace_title')}
              </p>
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="text-xs font-medium text-blue-600 hover:underline cursor-pointer"
                >
                  {t('reset_filters')}
                </button>
              )}
            </div>
          )}

          {/* Tasks List */}
          <ul className="divide-y divide-zinc-100">
            {visible.map(task => {
              const stage = currentStage(task.current_step);
              const isFieldwork = task.research_type === 'EMPIRICAL_HUMAN';
              const isComputational = task.research_type === 'EMPIRICAL_COMPUTATIONAL';

              return (
                <li key={task.id} className="p-4 sm:p-5 hover:bg-zinc-50/70 transition-colors">
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">

                    {/* Title & Info */}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium text-zinc-800 bg-zinc-100 border border-zinc-200">
                          {isComputational
                            ? (language === 'en' ? 'Computational' : 'Thực nghiệm tính toán')
                            : isFieldwork
                            ? (language === 'en' ? 'Fieldwork' : 'Thực nghiệm thực địa')
                            : (language === 'en' ? 'Literature Review' : 'Tổng quan tài liệu')}
                        </span>

                        <span className="text-zinc-300">•</span>
                        <span className="text-xs font-mono text-zinc-600">#{task.id.slice(0, 8)}</span>
                      </div>

                      <h3 className="break-words font-semibold text-zinc-900 text-sm sm:text-base">
                        {task.title}
                      </h3>

                      {/* Current Step & Iteration */}
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-zinc-700 font-medium">
                        <span className="text-zinc-600 font-normal">{t('mon_current_step')}:</span>
                        <span className="px-2 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-zinc-800">
                          {stage
                            ? `${language === 'en' ? (stage.name_en || stage.name) : stage.name} (${stage.agent})`
                            : task.current_step || (language === 'en' ? 'Step not recorded' : 'Chưa ghi nhận bước')}
                        </span>
                        <span className="text-zinc-300">•</span>
                        <span>{t('mon_iteration')} <strong className="font-mono text-zinc-800 font-medium">{task.current_iteration}</strong></span>
                        <span className="text-zinc-300">•</span>
                        <span className="font-normal text-zinc-600">{t('th_updated')}: <strong className="font-normal text-zinc-800">{formatTime(task.updated_at, language)}</strong></span>
                      </div>
                    </div>

                    {/* Status Pill & Action Buttons */}
                    <div className="flex flex-wrap items-center gap-2.5 shrink-0 pt-2 lg:pt-0">
                      <StatusPill status={task.status} />

                      {/* Monitor Detail Link */}
                      <Link
                        href={`/research/${task.id}/monitor`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 bg-white text-xs font-medium text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 transition-colors shadow-2xs"
                      >
                        <Activity size={13} className="text-blue-600" />
                        <span>{t('mon_open_detail')}</span>
                      </Link>

                      {/* Workspace Link */}
                      <Link
                        href={`/research/${task.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 bg-zinc-50 text-xs font-medium text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900 transition-colors shadow-2xs"
                      >
                        <span>{t('mon_open_workspace')}</span>
                        <ArrowUpRight size={13} />
                      </Link>
                    </div>

                  </div>
                </li>
              );
            })}
          </ul>

          {/* Pagination Footer */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 bg-zinc-50/60 p-3.5 sm:p-4 text-xs text-zinc-600">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage(p => Math.max(0, p - 1))}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors disabled:opacity-40 disabled:pointer-events-none shadow-2xs"
            >
              ← {t('mon_page_prev')}
            </button>

            <span className="font-medium">
              {t('mon_page_info')} {page + 1}
            </span>

            <button
              type="button"
              disabled={!data || data.length <= 20}
              onClick={() => setPage(p => p + 1)}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors disabled:opacity-40 disabled:pointer-events-none shadow-2xs"
            >
              {t('mon_page_next')} →
            </button>
          </div>
        </section>

      </div>
    </main>
  );
}
