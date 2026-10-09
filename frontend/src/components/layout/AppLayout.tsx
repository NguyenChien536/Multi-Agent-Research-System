'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, FileText, Menu, X, Plus } from 'lucide-react';
import { api } from '@/lib/api';
import type { ResearchTaskResponse } from '@/types';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);
  const [recentTasks, setRecentTasks] = React.useState<ResearchTaskResponse[]>([]);

  React.useEffect(() => {
    let active = true;
    api.tasks.list(0, 3).then(tasks => { if (active) setRecentTasks(tasks); }).catch(() => { if (active) setRecentTasks([]); });
    return () => { active = false; };
  }, [pathname]);

  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  ];

  return (
    <div className="flex h-screen bg-zinc-50 overflow-hidden text-zinc-900">
      {/* Mobile sidebar toggle */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-white border-b border-zinc-200 z-50 flex items-center justify-between px-4">
        <div className="flex items-center gap-2 font-bold text-lg">
          <div className="w-8 h-8 rounded-lg bg-zinc-900 text-white flex items-center justify-center text-sm">S</div>
          Synthia
        </div>
        <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2">
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-zinc-200 transform transition-transform duration-200 ease-in-out md:translate-x-0 md:static md:flex md:flex-col ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="h-16 flex items-center gap-2 px-6 border-b border-zinc-200 hidden md:flex">
          <div className="w-8 h-8 rounded-lg bg-zinc-900 text-white flex items-center justify-center text-sm font-bold shadow-sm">S</div>
          <span className="font-bold text-lg tracking-tight">Synthia</span>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2 pt-20 md:pt-4">
          <Link href="/" onClick={() => setIsMobileMenuOpen(false)} className="w-full flex items-center gap-2 bg-zinc-900 text-white px-4 py-2.5 rounded-xl hover:bg-zinc-800 transition-colors shadow-sm mb-4 font-medium">
              <Plus size={18} />
              <span>Nghiên cứu mới</span>
          </Link>

          <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 mt-4 px-2">Menu chính</div>
          <nav className="flex flex-col gap-1">
            {navItems.map((item) => {
              const isActive = pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link key={item.name} href={item.href} onClick={() => setIsMobileMenuOpen(false)}>
                  <div className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${isActive ? 'bg-zinc-100 text-zinc-900 font-medium' : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900'}`}>
                    <Icon size={18} className={isActive ? 'text-zinc-900' : 'text-zinc-400'} />
                    {item.name}
                  </div>
                </Link>
              );
            })}
          </nav>

          <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 mt-8 px-2">Gần đây</div>
          <nav className="flex flex-col gap-1">
            {recentTasks.length === 0 && <p className="px-3 text-xs text-zinc-400">Chưa có bài gần đây</p>}
            {recentTasks.map(task => (
              <Link key={task.id} href={`/research/${task.id}`} onClick={() => setIsMobileMenuOpen(false)} className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900 transition-colors text-sm">
                <FileText size={16} className="shrink-0 text-zinc-400" />
                <span className="truncate">{task.title}</span>
              </Link>
            ))}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden pt-16 md:pt-0">
        {children}
      </div>

      {/* Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-zinc-900/20 backdrop-blur-sm z-30 md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}
    </div>
  );
}
