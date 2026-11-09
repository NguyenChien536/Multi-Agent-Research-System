'use client';

import { Activity, AlertTriangle, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { statusLabel } from '@/lib/monitoring';
import { useLanguage } from '@/lib/i18n';

export function StatusPill({ status }: { status: string }) {
  const { language } = useLanguage();

  const dotColor = status === 'RUNNING'
    ? 'bg-blue-600 animate-pulse'
    : status === 'QUEUED'
    ? 'bg-zinc-400'
    : status === 'COMPLETED' || status === 'SUCCESS'
    ? 'bg-emerald-600'
    : status === 'FAILED'
    ? 'bg-red-600'
    : status.startsWith('WAITING') || status === 'NEEDS_REVIEW'
    ? 'bg-amber-600'
    : 'bg-zinc-400';

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-zinc-100/90 px-2.5 py-0.5 text-xs font-medium text-zinc-800">
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      <span>{statusLabel(status, language)}</span>
    </span>
  );
}

export function PollStatus({ error, lastSuccess, refresh, compact = false, details }: {
  error: string;
  lastSuccess: Date | null;
  refresh: () => void;
  compact?: boolean;
  details?: ReactNode;
}) {
  const { language } = useLanguage();
  const isEn = language === 'en';

  return (
    <div className="space-y-2.5">
      <div className={compact
        ? 'flex flex-wrap items-center gap-x-4 gap-y-2 text-xs font-normal text-zinc-600'
        : 'flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-700 bg-white px-4 py-2 rounded-xl border border-zinc-200 shadow-2xs font-normal'}>
        {details}
        <span className="flex items-center gap-2">
          <Activity size={14} className={error ? 'text-amber-600' : 'text-emerald-600'} />
          {lastSuccess ? (
            <span>
              {isEn ? 'Last synchronized: ' : 'Đồng bộ lúc: '}
              <strong className="font-mono text-zinc-800 font-medium">
                {lastSuccess.toLocaleTimeString(isEn ? 'en-US' : 'vi-VN')}
              </strong>
              {!compact && <span className="text-zinc-500 font-normal">
                {isEn ? ' (Auto-refreshes periodically)' : ' (Tự động cập nhật)'}
              </span>}
            </span>
          ) : error ? (
            <span className="text-amber-700 font-medium">
              {isEn ? 'Unable to reach monitoring server' : 'Chưa kết nối được với máy chủ giám sát'}
            </span>
          ) : (
            <span className="text-zinc-600 font-normal">
              {isEn ? 'Connecting to monitoring service...' : 'Đang kết nối lấy dữ liệu giám sát...'}
            </span>
          )}
        </span>

        <button
          type="button"
          onClick={refresh}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900 transition-colors shadow-2xs cursor-pointer"
        >
          <RefreshCw size={12} className="text-zinc-500" />
          <span>{isEn ? 'Refresh now' : 'Làm mới ngay'}</span>
        </button>
      </div>

      {error && (
        <div role="alert" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/80 p-3.5 text-xs text-amber-900 shadow-2xs font-normal">
          <AlertTriangle size={17} className="shrink-0 text-amber-600 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-900">
              {isEn ? 'Connection issue or delayed sync' : 'Mất kết nối hoặc chậm đồng bộ'}
            </p>
            <p className="text-amber-800">{error}</p>
            {lastSuccess && (
              <p className="text-amber-800/90 pt-0.5">
                {isEn
                  ? `Showing cached data from last successful fetch (${lastSuccess.toLocaleTimeString('en-US')}). Retrying in background.`
                  : `Dữ liệu đang hiển thị là dữ liệu lưu tạm từ lần nhận gần nhất (${lastSuccess.toLocaleTimeString('vi-VN')}). Hệ thống đang thử lại ngầm.`}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function formatTime(value: string | null | undefined, lang: 'en' | 'vi' = 'en') {
  if (!value) return lang === 'en' ? 'Not recorded' : 'Chưa ghi nhận';
  const locale = lang === 'en' ? 'en-US' : 'vi-VN';
  return new Date(value).toLocaleString(locale, { dateStyle: 'short', timeStyle: 'medium' });
}
