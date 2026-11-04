'use client';

import React from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Activity, FileText, MessageCircle, History } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';

export default function PaperLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { language } = useLanguage();
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
        className="flex shrink-0 flex-wrap gap-1.5 border-b border-zinc-200 bg-white px-5 py-2 print:hidden"
      >
        {tabs.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={isActive ? 'page' : undefined}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors ${
                isActive
                  ? 'bg-zinc-100 text-zinc-900 font-semibold border border-zinc-200 shadow-2xs'
                  : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950 font-medium'
              }`}
            >
              <Icon size={14} className={isActive ? 'text-zinc-900' : 'text-zinc-500'} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="min-h-0 flex-1 overflow-hidden print:overflow-visible">{children}</div>
    </div>
  );
}
