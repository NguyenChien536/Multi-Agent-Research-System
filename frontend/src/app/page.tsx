'use client';

import { useState, useEffect, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import {
  FileText, Search, ArrowRight, Settings2,
  ShieldCheck, ChevronDown, ChevronUp, LayoutDashboard, LogOut,
  FileUp, X, Cpu, FlaskConical, CheckCircle2, Globe
} from 'lucide-react';
import { api } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';
import type { ResearchType, UserResponse } from '@/types';


const OUTPUT_LANGUAGES = [
  { code: 'en', name: 'English', native: 'English (Default)', desc_en: 'Standard international scientific draft', desc_vi: 'Văn bản báo cáo chuẩn học thuật quốc tế' },
  { code: 'vi', name: 'Vietnamese', native: 'Tiếng Việt', desc_en: 'Standard Vietnamese academic draft', desc_vi: 'Bản thảo bài báo xuất bản bằng Tiếng Việt' },
  { code: 'ja', name: 'Japanese', native: '日本語', desc_en: 'Academic Japanese report format', desc_vi: 'Định dạng bài báo tiếng Nhật học thuật' },
  { code: 'zh', name: 'Chinese', native: '中文', desc_en: 'Standard academic Chinese report', desc_vi: 'Bản thảo khoa học bằng tiếng Trung chuẩn' },
  { code: 'fr', name: 'French', native: 'Français', desc_en: 'Academic French scientific draft', desc_vi: 'Báo cáo khoa học bằng tiếng Pháp' },
  { code: 'de', name: 'German', native: 'Deutsch', desc_en: 'Scientific German academic report', desc_vi: 'Báo cáo khoa học bằng tiếng Đức' },
  { code: 'es', name: 'Spanish', native: 'Español', desc_en: 'Academic Spanish scientific paper', desc_vi: 'Bài báo khoa học bằng tiếng Tây Ban Nha' },
  { code: 'ko', name: 'Korean', native: '한국어', desc_en: 'Academic Korean scientific report', desc_vi: 'Báo cáo khoa học bằng tiếng Hàn' },
];

export default function Home() {
  const router = useRouter();
  const { language, setLanguage, t } = useLanguage();
  const isEn = language === 'en';

  const [topic, setTopic] = useState('');
  const [researchType, setResearchType] = useState<ResearchType>('REVIEW');
  const [researchDepth, setResearchDepth] = useState<'SHALLOW' | 'STANDARD' | 'DEEP'>('STANDARD');
  const [reportLength, setReportLength] = useState<'SHORT' | 'MEDIUM' | 'LONG'>('MEDIUM');
  const [citationStyle, setCitationStyle] = useState<'IEEE' | 'APA' | 'HARVARD'>('IEEE');
  const [taskLanguage, setTaskLanguage] = useState<string>('en'); // Default to English
  const [requirePlanApproval, setRequirePlanApproval] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [error, setError] = useState('');
  const [hasSession, setHasSession] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);

  useEffect(() => {
    const has = api.auth.hasSession();
    setHasSession(has);
    if (has) {
      api.auth.me().then(setCurrentUser).catch(() => {});
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    const validPdfs: File[] = [];
    let err = '';

    for (const f of selected) {
      if (!f.name.toLowerCase().endsWith('.pdf') && f.type !== 'application/pdf') {
        err = isEn ? 'Only PDF files are supported.' : 'Chỉ chấp nhận tệp định dạng PDF.';
        continue;
      }
      if (f.size > 10 * 1024 * 1024) {
        err = isEn ? `File ${f.name} exceeds 10 MiB limit.` : `Tệp ${f.name} vượt quá dung lượng 10 MiB cho phép.`;
        continue;
      }
      validPdfs.push(f);
    }

    if (err) setError(err);

    setPdfFiles(prev => {
      const combined = [...prev, ...validPdfs];
      if (combined.length > 5) {
        setError(isEn ? 'Maximum 5 PDF files per research project.' : 'Tối đa 5 tài liệu PDF cho một bài nghiên cứu.');
        return combined.slice(0, 5);
      }
      return combined;
    });
    e.target.value = '';
  };

  const removePdfFile = (index: number) => {
    setPdfFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleStartResearch = async (e: FormEvent) => {
    e.preventDefault();
    const question = topic.trim();
    if (question.length < 10) {
      setError(isEn ? 'Please enter a research question with at least 10 characters.' : 'Vui lòng nhập câu hỏi nghiên cứu dài ít nhất 10 ký tự.');
      return;
    }
    if (!api.auth.hasSession()) {
      router.push('/login?next=%2F');
      return;
    }
    setError('');
    setIsLoading(true);
    try {
      const task = await api.tasks.create({
        title: question.slice(0, 255),
        research_question: question,
        research_type: researchType,
        research_depth: researchDepth,
        report_length: reportLength,
        citation_style: citationStyle,
        language: taskLanguage || 'en', // Default to English
        require_plan_approval: requirePlanApproval,
      });

      // Tải lên các file PDF riêng tư nếu có trước khi bắt đầu workflow
      if (pdfFiles.length > 0) {
        for (const file of pdfFiles) {
          await api.tasks.uploadPdf(task.id, file);
        }
      }

      await api.tasks.start(task.id);
      router.push(`/research/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : (isEn ? 'Unable to start research. Please try again.' : 'Không thể bắt đầu nghiên cứu. Vui lòng thử lại.'));
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    api.auth.logout();
    setHasSession(false);
    router.push('/login');
  };

  return (
    <div className="min-h-screen bg-[#fcfcfc] flex flex-col text-zinc-900 relative">
      {/* Header */}
      <header className="w-full px-6 py-4 flex justify-between items-center z-20 border-b border-zinc-200/80 bg-white/80 backdrop-blur-md">
        <div className="flex items-center gap-2.5 font-semibold text-lg tracking-tight">
          <div className="w-7 h-7 rounded-lg bg-zinc-900 text-white flex items-center justify-center text-xs font-semibold">S</div>
          <span className="text-zinc-900">Synthia</span>
        </div>

        {/* Clean, Non-redundant Navbar */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Quick Lang Switch */}
          <div className="flex items-center border border-zinc-200 rounded-lg p-0.5 bg-zinc-50 text-xs">
            <button
              type="button"
              onClick={() => setLanguage('en')}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                language === 'en' ? 'bg-white text-zinc-900 font-semibold shadow-2xs' : 'text-zinc-500 hover:text-zinc-800'
              }`}
              title="English (Default)"
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage('vi')}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                language === 'vi' ? 'bg-white text-zinc-900 font-semibold shadow-2xs' : 'text-zinc-500 hover:text-zinc-800'
              }`}
              title="Tiếng Việt"
            >
              VI
            </button>
          </div>

          {hasSession ? (
            <>
              {currentUser && (
                <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-100 border border-zinc-200 text-xs">
                  <div className="w-5 h-5 rounded-full bg-zinc-800 text-white flex items-center justify-center font-medium text-[10px]">
                    {(currentUser.full_name || currentUser.username || 'U')[0].toUpperCase()}
                  </div>
                  <span className="font-normal text-zinc-700 truncate max-w-[140px]">{currentUser.full_name || currentUser.username}</span>
                </div>
              )}
              <Button variant="outline" onClick={() => router.push('/dashboard')} className="text-xs h-8">
                <LayoutDashboard size={14} className="mr-1.5 text-zinc-500" /> {t('nav_dashboard')}
              </Button>
              <Button variant="ghost" onClick={handleLogout} title={t('nav_logout')} className="text-xs h-8">
                <LogOut size={14} className="mr-1 text-zinc-500" /> {t('nav_logout')}
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={() => router.push('/login')} className="text-xs h-8">
              {isEn ? 'Sign In / Register' : 'Đăng nhập / Đăng ký'}
            </Button>
          )}
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 z-10 max-w-4xl mx-auto w-full">
        <div className="w-full flex flex-col items-center gap-6 text-center animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="flex flex-col items-center gap-2">
            <h1 className="text-2xl sm:text-4xl font-bold tracking-tight text-zinc-900">
              {isEn ? 'What would you like to research today?' : 'Bạn muốn nghiên cứu gì hôm nay?'}
            </h1>
            <p className="text-zinc-600 max-w-xl text-xs sm:text-sm leading-relaxed font-normal">
              {isEn
                ? 'Automated scientific research platform for literature review, empirical analysis, and evidence-backed writing.'
                : 'Hệ thống nghiên cứu khoa học tự động hỗ trợ tổng quan tài liệu, phân tích thực nghiệm và soạn thảo bài báo có trích dẫn.'}
            </p>
          </div>

          <form onSubmit={handleStartResearch} className="w-full relative text-left">
            <div className={`absolute inset-0 bg-zinc-900/5 rounded-3xl blur-xl transition-opacity duration-500 pointer-events-none -z-10 ${isFocused ? 'opacity-100' : 'opacity-0'}`} />

            <div className="relative bg-white rounded-2xl shadow-xs border border-zinc-200 p-3 transition-all duration-200 focus-within:border-zinc-400 flex flex-col gap-2 z-10">
              <div className="flex items-start px-3 pt-2">
                <Search className="text-zinc-400 shrink-0 mr-3 mt-3" size={20} />
                <textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder={isEn
                    ? "Enter research question or topic (e.g., Evaluating quantum key distribution resilience against side-channel attacks...)"
                    : "Nhập câu hỏi hoặc chủ đề nghiên cứu (VD: Phân tích ảnh hưởng của trí tuệ nhân tạo đối với an ninh phần mềm...)"}
                  className="w-full resize-none border-0 bg-transparent py-2.5 text-sm sm:text-base text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-0 min-h-[80px]"
                  disabled={isLoading}
                  rows={2}
                />
              </div>

              {/* Bottom bar of prompt box */}
              <div className="flex flex-wrap items-center justify-between border-t border-zinc-100 px-3 py-2 bg-zinc-50/70 -mx-3 -mb-3 rounded-b-2xl gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-zinc-200 text-xs font-normal text-zinc-700 shadow-2xs">
                    {researchType === 'REVIEW' && <FileText size={13} className="text-zinc-500" />}
                    {researchType === 'EMPIRICAL_COMPUTATIONAL' && <Cpu size={13} className="text-purple-600" />}
                    {researchType === 'EMPIRICAL_HUMAN' && <FlaskConical size={13} className="text-emerald-600" />}
                    <span>
                      {researchType === 'REVIEW'
                        ? (isEn ? 'Literature Review' : 'Tổng quan tài liệu')
                        : researchType === 'EMPIRICAL_COMPUTATIONAL'
                        ? (isEn ? 'Computational' : 'Thực nghiệm tính toán')
                        : (isEn ? 'Fieldwork (Gate G4)' : 'Thực nghiệm thực địa (Gate G4)')}
                    </span>
                  </span>

                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium transition-colors shadow-2xs cursor-pointer ${showAdvanced ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100'}`}
                  >
                    <Settings2 size={13} className={showAdvanced ? 'text-white' : 'text-zinc-500'} />
                    <span>{isEn ? 'Configuration' : 'Cấu hình nghiên cứu'}</span>
                    {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || topic.trim().length < 10}
                  className="flex items-center gap-2 bg-zinc-900 text-white px-4 py-2 rounded-xl text-xs sm:text-sm font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs ml-auto cursor-pointer"
                >
                  {isLoading ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>{isEn ? 'Start Research' : 'Bắt đầu nghiên cứu'}</span>
                      <ArrowRight size={14} />
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Advanced Options Drawer with Interactive Clickable Cards */}
            {showAdvanced && (
              <div className="mt-3 bg-white rounded-xl border border-zinc-200 p-5 shadow-xs space-y-5 animate-in fade-in duration-150 z-10 relative">
                <div>
                  <h3 className="font-semibold text-sm text-zinc-900">
                    {isEn ? 'Research Configuration' : 'Tùy chọn cấu hình nghiên cứu'}
                  </h3>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {isEn ? 'Tune parameters, methodology, and output language' : 'Tùy biến các tham số cho chuỗi nghiên cứu'}
                  </p>
                </div>

                {/* 0. Research Type */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    {isEn ? 'Methodology' : 'Loại hình nghiên cứu'}
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    <button
                      type="button"
                      onClick={() => setResearchType('REVIEW')}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${researchType === 'REVIEW' ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs' : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-xs sm:text-sm">
                          {isEn ? 'Literature Review' : 'Tổng quan tài liệu'}
                        </div>
                        {researchType === 'REVIEW' && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                      </div>
                      <div className={`text-xs mt-0.5 ${researchType === 'REVIEW' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {isEn ? 'Systematic synthesis and claim extraction' : 'Review học thuật & tổng hợp từ tài liệu'}
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setResearchType('EMPIRICAL_COMPUTATIONAL')}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${researchType === 'EMPIRICAL_COMPUTATIONAL' ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs' : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-xs sm:text-sm">
                          {isEn ? 'Computational Empirical' : 'Thực nghiệm tính toán'}
                        </div>
                        {researchType === 'EMPIRICAL_COMPUTATIONAL' && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                      </div>
                      <div className={`text-xs mt-0.5 ${researchType === 'EMPIRICAL_COMPUTATIONAL' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {isEn ? 'Simulation protocol and data routine' : 'Đề cương mô phỏng & phân tích dữ liệu'}
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setResearchType('EMPIRICAL_HUMAN')}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${researchType === 'EMPIRICAL_HUMAN' ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs' : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-xs sm:text-sm">
                          {isEn ? 'Fieldwork (Gate G4)' : 'Thực nghiệm / Thực địa (Gate G4)'}
                        </div>
                        {researchType === 'EMPIRICAL_HUMAN' && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                      </div>
                      <div className={`text-xs mt-0.5 ${researchType === 'EMPIRICAL_HUMAN' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {isEn ? 'Protocol exported, pauses for field data' : 'Xuất đề cương, dừng chờ nạp số liệu thực địa'}
                      </div>
                    </button>
                  </div>
                </div>

                {/* 1. Research Depth (Cards) */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    {isEn ? 'Depth' : 'Độ sâu nghiên cứu'}
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    <button
                      type="button"
                      onClick={() => setResearchDepth('SHALLOW')}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${researchDepth === 'SHALLOW' ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs' : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-xs sm:text-sm">
                          {isEn ? 'Fast (SHALLOW)' : 'Nhanh (SHALLOW)'}
                        </div>
                        {researchDepth === 'SHALLOW' && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                      </div>
                      <div className={`text-xs mt-0.5 ${researchDepth === 'SHALLOW' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {isEn ? '1 iteration, ~5 sources' : '1 vòng nghiên cứu, ~5 nguồn'}
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setResearchDepth('STANDARD')}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${researchDepth === 'STANDARD' ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs' : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-xs sm:text-sm">
                          {isEn ? 'Standard (STANDARD)' : 'Tiêu chuẩn (STANDARD)'}
                        </div>
                        {researchDepth === 'STANDARD' && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                      </div>
                      <div className={`text-xs mt-0.5 ${researchDepth === 'STANDARD' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {isEn ? '2 iterations, ~10 sources' : '2 vòng nghiên cứu, ~10 nguồn'}
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setResearchDepth('DEEP')}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${researchDepth === 'DEEP' ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs' : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-xs sm:text-sm">
                          {isEn ? 'Comprehensive (DEEP)' : 'Chuyên sâu (DEEP)'}
                        </div>
                        {researchDepth === 'DEEP' && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                      </div>
                      <div className={`text-xs mt-0.5 ${researchDepth === 'DEEP' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {isEn ? '3 iterations, ~20 sources' : '3 vòng nghiên cứu, ~20 nguồn'}
                      </div>
                    </button>
                  </div>
                </div>

                {/* 2 & 3. Length & Citation */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1 border-t border-zinc-100">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600">
                      {isEn ? 'Report Length' : 'Độ dài bài báo'}
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['SHORT', 'MEDIUM', 'LONG'] as const).map((len) => (
                        <button
                          key={len}
                          type="button"
                          onClick={() => setReportLength(len)}
                          className={`py-1.5 px-2.5 rounded-lg border text-xs font-medium text-center transition-all cursor-pointer ${reportLength === len ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-zinc-50 border-zinc-200 text-zinc-700 hover:bg-zinc-100'}`}
                        >
                          {len === 'SHORT' ? (isEn ? 'Short' : 'Ngắn') : len === 'MEDIUM' ? (isEn ? 'Medium' : 'Vừa') : (isEn ? 'Long' : 'Dài')}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600">
                      {isEn ? 'Citation Style' : 'Kiểu trích dẫn'}
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['IEEE', 'APA', 'HARVARD'] as const).map((style) => (
                        <button
                          key={style}
                          type="button"
                          onClick={() => setCitationStyle(style)}
                          className={`py-1.5 px-2.5 rounded-lg border text-xs font-medium text-center transition-all cursor-pointer ${citationStyle === style ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-zinc-50 border-zinc-200 text-zinc-700 hover:bg-zinc-100'}`}
                        >
                          {style}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Report Output Language Configuration (Configurable to English or other languages) */}
                <div className="space-y-2 pt-2 border-t border-zinc-100">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600">
                      {isEn ? 'Paper Output Language' : 'Ngôn ngữ bài báo xuất bản'}
                    </label>
                    <span className="text-xs font-semibold text-zinc-700 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
                      {OUTPUT_LANGUAGES.find(l => l.code === taskLanguage)?.native || taskLanguage.toUpperCase()}
                    </span>
                  </div>

                  {/* Primary Language Choices (English & Vietnamese) */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {OUTPUT_LANGUAGES.slice(0, 2).map(lang => (
                      <button
                        key={lang.code}
                        type="button"
                        onClick={() => setTaskLanguage(lang.code)}
                        className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                          taskLanguage === lang.code
                            ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs'
                            : 'border-zinc-200 bg-zinc-50/70 hover:bg-zinc-100 text-zinc-800'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs sm:text-sm">{lang.native}</span>
                          {taskLanguage === lang.code && <CheckCircle2 size={14} className="text-emerald-400" />}
                        </div>
                        <div className={`text-xs mt-0.5 ${taskLanguage === lang.code ? 'text-zinc-300' : 'text-zinc-500'}`}>
                          {isEn ? lang.desc_en : lang.desc_vi}
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Additional International Languages */}
                  <div>
                    <span className="block text-[11px] font-medium text-zinc-500 mb-1.5">
                      {isEn ? 'Or publish in other languages:' : 'Hoặc xuất bản bằng các ngôn ngữ khác:'}
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {OUTPUT_LANGUAGES.slice(2).map(lang => (
                        <button
                          key={lang.code}
                          type="button"
                          onClick={() => setTaskLanguage(lang.code)}
                          className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                            taskLanguage === lang.code
                              ? 'border-zinc-900 bg-zinc-900 text-white shadow-2xs'
                              : 'border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700'
                          }`}
                        >
                          <span>{lang.native}</span>
                          <span className={`text-[10px] ${taskLanguage === lang.code ? 'text-zinc-300' : 'text-zinc-400'}`}>({lang.name})</span>
                          {taskLanguage === lang.code && <CheckCircle2 size={12} className="text-emerald-400" />}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* HITL Plan Review */}
                <div className="border-t border-zinc-100 pt-3">
                  <button
                    type="button"
                    onClick={() => setRequirePlanApproval(!requirePlanApproval)}
                    className={`w-full p-3 rounded-xl border text-left flex items-start gap-2.5 transition-colors cursor-pointer ${requirePlanApproval ? 'bg-zinc-100/90 border-zinc-400 ring-1 ring-zinc-400' : 'bg-zinc-50 border-zinc-200 hover:bg-zinc-100'}`}
                  >
                    <div className="mt-0.5">
                      <input
                        type="checkbox"
                        checked={requirePlanApproval}
                        onChange={() => {}}
                        className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-3.5 h-3.5 cursor-pointer"
                      />
                    </div>
                    <div>
                      <div className="font-semibold text-xs text-zinc-900 flex items-center gap-1.5">
                        <ShieldCheck size={14} className="text-blue-600" />
                        {isEn ? 'Require Plan Approval (Human-in-the-Loop)' : 'Chế độ phê duyệt đề cương (Human-in-the-Loop)'}
                      </div>
                      <div className="text-xs text-zinc-500 mt-0.5 leading-relaxed">
                        {isEn
                          ? 'Workflow pauses after planning for you to review and approve research queries before gathering sources.'
                          : 'Hệ thống sẽ tạm dừng sau giai đoạn Supervisor để bạn xem và duyệt đề cương trước khi bắt đầu tìm nguồn.'}
                      </div>
                    </div>
                  </button>
                </div>

                {/* Private PDF Upload */}
                <div className="border-t border-zinc-100 pt-3 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-xs text-zinc-900 flex items-center gap-1.5">
                        <FileUp size={13} className="text-zinc-600" />
                        {isEn ? 'Upload Private PDF Documents (Optional)' : 'Nạp tài liệu PDF riêng tư (Tùy chọn)'}
                      </h4>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {isEn
                          ? 'Custom papers will be parsed, chunked, and indexed into this project\'s vector knowledge store.'
                          : 'Tài liệu riêng sẽ được trích xuất text, băm nhỏ và nhúng vector vào tri thức nghiên cứu của bài.'}
                      </p>
                    </div>
                    <span className="text-xs text-zinc-600 font-medium shrink-0">Max 5 files, 10 MiB</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5">
                    <label className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-50 hover:bg-zinc-100 border border-dashed border-zinc-300 text-xs font-medium text-zinc-700 cursor-pointer transition-colors">
                      <FileUp size={13} className="text-zinc-500" />
                      <span>{isEn ? 'Select PDF file' : 'Chọn file PDF tải lên'}</span>
                      <input
                        type="file"
                        accept=".pdf,application/pdf"
                        multiple
                        className="hidden"
                        onChange={handleFileSelect}
                      />
                    </label>
                    <span className="text-xs text-zinc-600 font-medium">
                      {pdfFiles.length === 0 ? (isEn ? 'No files selected' : 'Chưa chọn file nào') : `${pdfFiles.length}/5 PDFs`}
                    </span>
                  </div>

                  {pdfFiles.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                      {pdfFiles.map((file, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-zinc-50 border border-zinc-200 text-xs">
                          <div className="flex items-center gap-2 truncate pr-2">
                            <FileText size={13} className="text-zinc-500 shrink-0" />
                            <span className="truncate font-medium text-zinc-800">{file.name}</span>
                            <span className="text-xs text-zinc-600 font-medium shrink-0">({(file.size / 1024 / 1024).toFixed(2)} MB)</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removePdfFile(idx)}
                            className="text-zinc-400 hover:text-red-500 p-0.5 rounded transition-colors cursor-pointer"
                            title="Remove"
                          >
                            <X size={13} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </form>

          {error && (
            <p role="alert" className="text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg px-3.5 py-2 text-center">
              {error}
            </p>
          )}

          {/* Clean Scientific Features Badges (No decorative buzzwords) */}
          <div className="flex flex-wrap justify-center gap-2 text-xs text-zinc-600 mt-1">
            <span className="px-2.5 py-1 rounded-full bg-zinc-100 border border-zinc-200 font-normal">
              {isEn ? 'Academic literature synthesis' : 'Tổng hợp tài liệu học thuật'}
            </span>
            <span className="px-2.5 py-1 rounded-full bg-zinc-100 border border-zinc-200 font-normal">
              {isEn ? 'Multi-pass evidence verification' : 'Đối chiếu & kiểm chứng bằng chứng'}
            </span>
            <span className="px-2.5 py-1 rounded-full bg-zinc-100 border border-zinc-200 font-normal">
              {isEn ? 'Traceable citation audit trail' : 'Trích dẫn có thể xác minh nguồn'}
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
