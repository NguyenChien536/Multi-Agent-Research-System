'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, LayoutDashboard, Globe } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';

export function ResearchNavigation() {
  const pathname = usePathname();
  const { language, setLanguage, t } = useLanguage();

  const isDashboard = pathname === '/dashboard';
  const isMonitor = pathname.startsWith('/research/monitor') || pathname.endsWith('/monitor');

  return (
    <nav aria-label="Research Navigation" className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-white px-5 py-2.5 text-xs print:hidden shadow-2xs">
      <div className="flex items-center gap-2 text-zinc-700">
        <span className="font-semibold text-zinc-900 tracking-tight">Synthia Platform</span>
        <span className="text-zinc-300">•</span>
        <span className="text-zinc-600 font-normal">
          {isMonitor ? t('nav_monitor') : t('nav_dashboard')}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <Link
          href="/dashboard"
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-colors ${
            isDashboard
              ? 'bg-zinc-100 text-zinc-900 border border-zinc-200'
              : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50'
          }`}
        >
          <LayoutDashboard size={14} className={isDashboard ? 'text-zinc-900' : 'text-zinc-500'} />
          <span>{t('nav_dashboard')}</span>
        </Link>

        <Link
          href="/research/monitor"
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-colors ${
            isMonitor
              ? 'bg-zinc-100 text-zinc-900 border border-zinc-200'
              : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50'
          }`}
        >
          <Activity size={14} className={isMonitor ? 'text-zinc-900' : 'text-zinc-500'} />
          <span>{t('nav_monitor')}</span>
        </Link>

        {/* Quick Language Toggle Pill */}
        <div className="flex items-center border border-zinc-200 rounded-md p-0.5 bg-zinc-50 ml-1">
          <button
            type="button"
            onClick={() => setLanguage('en')}
            className={`px-1.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
              language === 'en' ? 'bg-white text-zinc-900 shadow-2xs font-semibold' : 'text-zinc-500 hover:text-zinc-800'
            }`}
            title="English (Default)"
          >
            EN
          </button>
          <button
            type="button"
            onClick={() => setLanguage('vi')}
            className={`px-1.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
              language === 'vi' ? 'bg-white text-zinc-900 shadow-2xs font-semibold' : 'text-zinc-500 hover:text-zinc-800'
            }`}
            title="Tiếng Việt"
          >
            VI
          </button>
        </div>
      </div>
    </nav>
  );
}
