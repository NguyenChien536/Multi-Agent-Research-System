'use client';

import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Activity, FileText, MessageCircle } from 'lucide-react';

export default function PaperLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const tabs = [
    { href: `/research/${id}`, label: 'Bài nghiên cứu', icon: FileText },
    { href: `/research/${id}/monitor`, label: 'Tiến độ', icon: Activity },
    { href: `/research/${id}/questions`, label: 'Hỏi về bài báo', icon: MessageCircle },
  ];
  return <div className="flex h-full min-h-0 flex-col print:h-auto">
    <nav aria-label="Các trang của bài nghiên cứu" className="flex shrink-0 flex-wrap gap-1 border-b border-zinc-200 bg-white px-4 py-1.5 print:hidden">
      {tabs.map(({ href, label, icon: Icon }) => <Link key={href} href={href}
        aria-current={pathname === href ? 'page' : undefined}
        className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${pathname === href ? 'bg-blue-50 text-blue-700' : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900'}`}>
        <Icon size={14} />{label}
      </Link>)}
    </nav>
    <div className="min-h-0 flex-1 overflow-hidden print:overflow-visible">{children}</div>
  </div>;
}
