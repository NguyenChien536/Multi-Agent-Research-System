'use client';

import React from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Activity, FileText, MessageCircle, History, ArrowLeft } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';

export default function PaperLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { language, t } = useLanguage();
  const isEn = language === 'en';

  const tabs = [
    {
      href: `/research/${id}`,
      label: isEn ? 'Research Paper' : 'Bài nghiên cứu',
      icon: FileText,
    },
    {
      href: `/research/${id}/monitor`,
      label: isEn ? 'Live Monitor' : 'Tiến độ giám sát',
      icon: Activity,
    },
    {
      href: `/research/${id}/questions`,
      label: isEn ? 'Q&A Assistant' : 'Hỏi đáp bài báo',
      icon: MessageCircle,
    },
    {
      href: `/research/${id}/revisions`,
      label: isEn ? 'Editorial Revisions' : 'Lịch sử chỉnh sửa',
      icon: History,
    },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col print:h-auto">
      <nav
        aria-label={isEn ? "Research Paper Navigation" : "Các trang của bài nghiên cứu"}
        className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 sm:px-6 py-2.5 print:hidden shadow-2xs z-20"
      >
        {/* Breadcrumb / Back */}
        <div className="flex items-center gap-2 text-xs">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 font-medium text-zinc-500 hover:text-zinc-900 transition-colors p-1 -ml-1 rounded-md hover:bg-zinc-100"
            title={isEn ? "Back to Dashboard" : "Quay lại Dashboard"}
          >
            <ArrowLeft size={14} />
            <span>{t('nav_dashboard')}</span>
          </Link>
          <span className="text-zinc-300">/</span>
          <span className="font-mono text-zinc-500 font-medium">
            #{id?.slice(0, 8)}
          </span>
        </div>

        {/* Tab links */}
        <div className="flex items-center gap-1 sm:gap-1.5 overflow-x-auto">
          {tabs.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? 'page' : undefined}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-colors shrink-0 ${
                  isActive
                    ? 'bg-zinc-900 text-white font-semibold shadow-2xs'
                    : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 font-medium'
                }`}
              >
                <Icon size={14} className={isActive ? 'text-white' : 'text-zinc-500'} />
                <span>{label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
      <div className="min-h-0 flex-1 overflow-hidden print:overflow-visible">{children}</div>
    </div>
  );
}
