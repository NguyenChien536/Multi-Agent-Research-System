'use client';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ModelSettingsPanel } from '@/components/ModelSettingsPanel';
import { useLanguage } from '@/lib/i18n';
export default function SettingsPage() {
  const {language} = useLanguage();
  const isEn = language === 'en';
  return <AppLayout><main className="flex-1 overflow-y-auto p-6 sm:p-10"><div className="mx-auto max-w-xl space-y-6">
    <div className="flex items-center justify-between gap-3"><h1 className="text-2xl font-semibold">Settings</h1>
      <Link href="/" className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white">{isEn?'New research':'Tạo bài nghiên cứu'}</Link></div>
    <div className="rounded-2xl border border-zinc-200 bg-white p-5"><ModelSettingsPanel isEn={isEn} /></div>
  </div></main></AppLayout>;
}
