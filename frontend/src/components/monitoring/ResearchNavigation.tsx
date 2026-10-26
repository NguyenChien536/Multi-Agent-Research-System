import Link from 'next/link';
import { Activity, LayoutDashboard } from 'lucide-react';

export function ResearchNavigation() {
  return (
    <nav aria-label="Điều hướng nghiên cứu" className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 py-2.5 text-xs font-semibold print:hidden shadow-sm">
      <div className="hidden items-center gap-2 text-zinc-800 lg:flex">
        <Activity size={14} className="text-blue-600" />
        <span className="font-bold tracking-tight text-zinc-900">Synthia Multi-Agent Engine</span>
        <span className="text-zinc-400">•</span>
        <span className="text-zinc-600 font-medium">Bảng điều phối nghiên cứu</span>
      </div>
      <div className="flex flex-wrap items-center gap-3 sm:gap-5">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-zinc-600 hover:text-zinc-950 transition-colors font-semibold"
        >
          <LayoutDashboard size={14} className="text-zinc-600" />
          Danh sách bài nghiên cứu
        </Link>
        <Link
          href="/research/monitor"
          className="inline-flex items-center gap-1.5 font-bold text-blue-700 hover:text-blue-900 transition-colors bg-blue-50 px-2.5 py-1 rounded-lg border border-blue-200/80"
        >
          <Activity size={14} className="text-blue-600" />
          Giám sát hoạt động Agent & Sổ cái chi phí
        </Link>
      </div>
    </nav>
  );
}
