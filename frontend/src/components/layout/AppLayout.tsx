'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard, FileText, Menu, X, Plus, LogOut,
  Activity, Settings, Globe, Check
} from 'lucide-react';
import { api } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';
import type { ResearchTaskResponse, UserResponse } from '@/types';
import { ModelSettingsPanel } from '@/components/ModelSettingsPanel';
import { ProfileSettingsPanel } from '@/components/ProfileSettingsPanel';
import { useDialogFocus } from '@/lib/use-dialog-focus';

const DEFAULT_SIDEBAR_WIDTH = 260;
const MIN_SIDEBAR_WIDTH = 220;
const MAX_SIDEBAR_WIDTH = 520; // 2x default width

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { language, setLanguage, t } = useLanguage();

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<'ai' | 'profile' | 'language'>('ai');
  const settingsDialog = useDialogFocus(isSettingsOpen, () => setIsSettingsOpen(false));
  const [recentTasks, setRecentTasks] = useState<ResearchTaskResponse[]>([]);
  const [user, setUser] = useState<UserResponse | null>(null);
  useEffect(() => {
    const updated = (event: Event) => setUser((event as CustomEvent<UserResponse>).detail);
    window.addEventListener('synthia-profile-updated', updated);
    return () => window.removeEventListener('synthia-profile-updated', updated);
  }, []);
  useEffect(() => {
    const open = () => setIsSettingsOpen(true);
    window.addEventListener('synthia-open-settings', open);
    return () => window.removeEventListener('synthia-open-settings', open);
  }, []);

  // Resizable sidebar state
  const [sidebarWidth, setSidebarWidth] = useState<number>(DEFAULT_SIDEBAR_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const widthRef = useRef(sidebarWidth);
  widthRef.current = sidebarWidth;

  // Restore saved sidebar width from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('synthia_sidebar_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= MIN_SIDEBAR_WIDTH && parsed <= MAX_SIDEBAR_WIDTH) {
          setSidebarWidth(parsed);
          widthRef.current = parsed;
        }
      }
    } catch {}
  }, []);

  // Handle resizing mouse events
  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
  }, []);

  const resetWidth = useCallback(() => {
    setSidebarWidth(DEFAULT_SIDEBAR_WIDTH);
    widthRef.current = DEFAULT_SIDEBAR_WIDTH;
    try {
      localStorage.setItem('synthia_sidebar_width', String(DEFAULT_SIDEBAR_WIDTH));
    } catch {}
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.min(Math.max(e.clientX, MIN_SIDEBAR_WIDTH), MAX_SIDEBAR_WIDTH);
      setSidebarWidth(newWidth);
      widthRef.current = newWidth;
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      try {
        localStorage.setItem('synthia_sidebar_width', String(widthRef.current));
      } catch {}
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isResizing]);

  // Auth and Recent Tasks loading
  useEffect(() => {
    if (!api.auth.hasSession()) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    let active = true;
    api.auth.me().then(u => { if (active) setUser(u); }).catch(() => {});
    api.tasks.list(0, 8).then(tasks => {
      if (!active) return;
      const match = pathname.match(/^\/research\/([^/]+)/);
      const currentTaskId = match ? match[1] : null;
      if (currentTaskId && currentTaskId !== 'monitor' && !tasks.some(t => t.id === currentTaskId)) {
        api.tasks.get(currentTaskId).then(currentTask => {
          if (active && currentTask) {
            setRecentTasks([currentTask, ...tasks]);
          }
        }).catch(() => {
          if (active) setRecentTasks(tasks);
        });
      } else {
        setRecentTasks(tasks);
      }
    }).catch(() => { if (active) setRecentTasks([]); });
    return () => { active = false; };
  }, [pathname, router]);

  const navItems = [
    { name: t('nav_dashboard'), href: '/dashboard', icon: LayoutDashboard },
    { name: t('nav_monitor'), href: '/research/monitor', icon: Activity },
  ];

  return (
    <div className="flex h-screen bg-white overflow-hidden text-stone-900 print:h-auto print:overflow-visible print:bg-white">

      {/* Mobile Header */}
      <div id="mobile-header" className="md:hidden fixed top-0 left-0 right-0 h-16 bg-white/95 backdrop-blur-md border-b border-stone-200/80 z-50 flex items-center justify-between px-4 print:hidden">
        <div className="flex items-center gap-2 font-semibold text-base">
          <div className="w-8 h-8 rounded-xl bg-stone-900 text-white flex items-center justify-center text-sm font-semibold shadow-2xs">S</div>
          <span>Synthia</span>
        </div>
        <div className="flex items-center gap-2">
          {/* Quick Lang Switch */}
          <button
            type="button"
            onClick={() => setLanguage(language === 'en' ? 'vi' : 'en')}
            className="px-2 py-1 rounded-md text-xs font-semibold text-zinc-700 border border-zinc-200 hover:bg-zinc-100"
            title={language === 'en' ? 'Chuyển sang Tiếng Việt' : 'Switch to English'}
          >
            {language === 'en' ? 'EN' : 'VI'}
          </button>
          <button type="button" aria-label={isMobileMenuOpen ? (language==='en'?'Close navigation':'Đóng điều hướng') : (language==='en'?'Open navigation':'Mở điều hướng')} aria-expanded={isMobileMenuOpen} aria-controls="app-sidebar" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2 text-zinc-700">
            {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Sidebar: Resizable on desktop, slideover on mobile */}
      <aside
        id="app-sidebar"
        style={{ width: `${sidebarWidth}px` }}
        className={`fixed inset-y-0 left-0 z-40 bg-white border-r border-stone-200/80 md:relative flex flex-col print:hidden shrink-0 ${
          isResizing ? '' : 'transition-[width] duration-75'
        } ${
          isMobileMenuOpen ? 'visible translate-x-0 w-72' : 'invisible -translate-x-full md:visible md:translate-x-0'
        }`}
      >
        {/* Resize Handle on Desktop */}
        <div
          onMouseDown={startResizing}
          onDoubleClick={resetWidth}
          title="Drag to resize sidebar (Double-click to reset)"
          className={`hidden md:block absolute top-0 right-0 w-2 h-full cursor-col-resize z-50 group hover:bg-stone-300/80 transition-colors ${
            isResizing ? 'bg-stone-400' : 'bg-transparent'
          }`}
        >
          <div className="absolute top-1/2 -translate-y-1/2 right-0.5 w-1 h-8 rounded-full bg-stone-300 group-hover:bg-stone-500 transition-colors" />
        </div>

        {/* Brand */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-stone-200/80 hidden md:flex shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-zinc-900 text-white flex items-center justify-center text-sm font-semibold">S</div>
            <span className="font-semibold text-lg tracking-tight text-stone-900">Synthia</span>
          </div>

          {/* Quick Language Toggle */}
          <div className="flex items-center rounded-full border border-stone-300/80 p-0.5 bg-stone-100 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setLanguage('en')}
              className={`px-2 py-0.5 rounded transition-colors ${
                language === 'en' ? 'bg-white text-stone-900 font-semibold shadow-2xs rounded-full' : 'text-stone-600 hover:text-stone-900 rounded-full'
              }`}
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage('vi')}
              className={`px-2 py-0.5 rounded transition-colors ${
                language === 'vi' ? 'bg-white text-stone-900 font-semibold shadow-2xs rounded-full' : 'text-stone-600 hover:text-stone-900 rounded-full'
              }`}
            >
              VI
            </button>
          </div>
        </div>

        {/* Sidebar Nav Content */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-1 pt-20 md:pt-4">
          <Link
            href="/"
            onClick={() => setIsMobileMenuOpen(false)}
            className="w-full flex items-center justify-center gap-2 bg-stone-900 text-white px-4 py-2.5 rounded-xl hover:bg-stone-800 transition-all shadow-xs mb-3 font-medium text-sm sm:text-[15px] cursor-pointer"
          >
            <Plus size={17} />
            <span>{t('nav_new_research')}</span>
          </Link>

          {/* Section: Main Menu */}
          <div className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-2 px-3">
            {t('nav_main_menu')}
          </div>

          <nav className="flex flex-col gap-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <Link key={item.href} href={item.href} onClick={() => setIsMobileMenuOpen(false)}>
                  <div className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm sm:text-[15px] transition-all cursor-pointer ${
                    isActive
                      ? 'bg-stone-100 text-stone-950 font-semibold border border-stone-200/80 shadow-2xs'
                      : 'text-stone-700 hover:bg-stone-100 hover:text-stone-950 font-medium'
                  }`}>
                    <Icon size={18} className={isActive ? 'text-stone-900' : 'text-stone-500'} />
                    <span>{item.name}</span>
                  </div>
                </Link>
              );
            })}
          </nav>

          {/* Section: Recent Tasks */}
          <div className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-6 px-3">
            {t('nav_recent')}
          </div>
          <nav className="flex flex-col gap-1">
            {recentTasks.length === 0 && (
              <p className="px-3.5 text-xs text-zinc-500 py-1.5">{t('nav_no_recent')}</p>
            )}
            {recentTasks.map(task => {
              const isSelected = pathname.startsWith(`/research/${task.id}`);
              return (
                <Link
                  key={task.id}
                  href={`/research/${task.id}`}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`group flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-sm transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-stone-100 text-stone-950 font-semibold border border-stone-200/80 shadow-2xs'
                      : 'text-stone-700 hover:bg-stone-100 hover:text-stone-900'
                  }`}
                  title={task.title}
                >
                  <FileText
                    size={16}
                    className={`shrink-0 transition-colors ${
                      isSelected ? 'text-stone-900' : 'text-stone-500 group-hover:text-stone-800'
                    }`}
                  />
                  <span className="truncate">{task.title}</span>
                </Link>
              );
            })}
          </nav>

          {/* Footer Area */}
          <div className="mt-auto pt-3 border-t border-stone-200/80 flex flex-col gap-1.5 shrink-0">
            {user && (
              <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-stone-50 border border-stone-200/80 text-xs">
                <div className="w-7 h-7 rounded-lg bg-stone-900 text-white flex items-center justify-center font-semibold text-xs shrink-0">
                  {(user.full_name || user.username || 'U')[0].toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-stone-900 text-sm truncate">{user.full_name || user.username}</div>
                  <div className="text-xs text-stone-600 truncate">{user.email}</div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between gap-1 pt-1">
              <button
                type="button"
                onClick={() => setIsSettingsOpen(true)}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 hover:text-stone-950 transition-colors cursor-pointer"
              >
                <Settings size={16} className="text-zinc-500" />
                <span>{t('nav_settings')}</span>
              </button>

              <button
                type="button"
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-stone-700 hover:bg-rose-50 hover:text-rose-700 transition-colors cursor-pointer"
                onClick={() => { api.auth.logout(); router.replace('/login'); }}
                title={t('nav_logout')}
              >
                <LogOut size={16} />
                <span>{t('nav_logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area: flex flex-col h-full ensures reliable scrolling */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden pt-16 md:pt-0 print:pt-0 print:overflow-visible print:h-auto print:block">
        {children}
      </div>

      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-zinc-900/20 backdrop-blur-sm z-30 md:hidden print:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Settings Modal (Cài đặt hệ thống & Chuyển ngôn ngữ sang Tiếng Anh / Tiếng Việt) */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-zinc-900/40 backdrop-blur-xs">
          <div ref={settingsDialog} role="dialog" aria-modal="true" aria-labelledby="app-settings-title" tabIndex={-1} className="w-full max-w-2xl max-h-[90dvh] overflow-y-auto bg-white rounded-2xl border border-zinc-200 shadow-xl outline-none">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/70">
              <div className="flex items-center gap-2">
                <Settings size={18} className="text-zinc-700" />
                <h3 id="app-settings-title" className="font-semibold text-base text-zinc-900">
                  {t('settings_title')}
                </h3>
              </div>
              <button
                type="button"
                aria-label={language==='en'?'Close settings':'Đóng cài đặt'}
                onClick={() => setIsSettingsOpen(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5 text-sm">
              <div className="flex flex-wrap gap-2" aria-label={language==='en'?'Settings sections':'Các mục cài đặt'}>
                {(['ai','profile','language'] as const).map(tab=><button key={tab} type="button" aria-pressed={settingsTab===tab} onClick={()=>setSettingsTab(tab)} className={`rounded-lg px-3 py-2 font-medium ${settingsTab===tab?'bg-stone-900 text-white':'bg-stone-100 text-stone-700'}`}>
                  {tab==='ai'?(language==='en'?'AI connection':'Kết nối AI'):tab==='profile'?(language==='en'?'Profile':'Tài khoản'):(language==='en'?'Language':'Ngôn ngữ')}
                </button>)}
              </div>
              {settingsTab==='profile' && <ProfileSettingsPanel isEn={language === 'en'} />}
              {settingsTab==='ai' && <ModelSettingsPanel isEn={language === 'en'} taskId={pathname.match(/^\/research\/([0-9a-f-]{36})(?:\/|$)/i)?.[1]} />}

              {/* Language Selection Setting */}
              <div className={settingsTab==='language'?'space-y-2.5':'hidden'}>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-700">
                  {t('settings_lang_label')}
                </label>
                <p className="text-xs text-zinc-600">
                  {t('settings_lang_desc')}
                </p>

                <div className="grid grid-cols-1 gap-2 pt-1">
                  {/* English Option (DEFAULT) */}
                  <button
                    type="button"
                    onClick={() => setLanguage('en')}
                    className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                      language === 'en'
                        ? 'border-zinc-900 bg-zinc-50 ring-1 ring-zinc-900'
                        : 'border-zinc-200 hover:border-zinc-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Globe size={18} className={language === 'en' ? 'text-zinc-900' : 'text-zinc-400'} />
                      <div>
                        <div className="font-medium text-zinc-900 flex items-center gap-2">
                          {t('settings_lang_en')}
                          <span className="text-[10px] px-2 py-0.2 rounded-full font-medium bg-zinc-200 text-zinc-800">
                            {t('settings_default_badge')}
                          </span>
                        </div>
                        <div className="text-xs text-zinc-600 mt-0.5">
                          Standard international scientific terminology
                        </div>
                      </div>
                    </div>
                    {language === 'en' && <Check size={18} className="text-zinc-900" />}
                  </button>

                  {/* Vietnamese Option */}
                  <button
                    type="button"
                    onClick={() => setLanguage('vi')}
                    className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                      language === 'vi'
                        ? 'border-zinc-900 bg-zinc-50 ring-1 ring-zinc-900'
                        : 'border-zinc-200 hover:border-zinc-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Globe size={18} className={language === 'vi' ? 'text-zinc-900' : 'text-zinc-400'} />
                      <div>
                        <div className="font-medium text-zinc-900">
                          {t('settings_lang_vi')}
                        </div>
                        <div className="text-xs text-zinc-600 mt-0.5">
                          Giao diện chuẩn hóa ngôn ngữ Tiếng Việt
                        </div>
                      </div>
                    </div>
                    {language === 'vi' && <Check size={18} className="text-zinc-900" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 bg-zinc-50 border-t border-zinc-200 flex justify-end">
              <button
                type="button"
                onClick={() => setIsSettingsOpen(false)}
                className="px-4 py-2 rounded-xl bg-zinc-900 text-white font-medium text-xs hover:bg-zinc-800 transition-colors shadow-2xs"
              >
                {t('settings_close')}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
