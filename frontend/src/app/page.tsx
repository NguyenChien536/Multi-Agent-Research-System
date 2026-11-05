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
import { ModelSettingsPanel } from '@/components/ModelSettingsPanel';
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

const DRAFT_STORAGE_KEY = 'synthia_draft_research';

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
  const [maxSources, setMaxSources] = useState(12);
  const [useServerProviders, setUseServerProviders] = useState(false);
  const [savedModel, setSavedModel] = useState<string | null>(null);
  const [modelStatus, setModelStatus] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading');
  const [showModelSettings, setShowModelSettings] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = () => {
      if (!api.auth.hasSession()) return;
      api.tasks.modelConnectionOptions().then(options => {
        if (active) setUseServerProviders(!!options.use_server_providers);
        if (options.use_server_providers) {
          if (active) { setSavedModel((options.server_provider || 'Server') + ' (.env)'); setModelStatus(options.server_provider_ready ? 'ready' : 'error'); }
          return null;
        }
        return api.settings.getModelConnection();
      }).then(result => {
        if (!result) return;
        if (!active) return;
        const ready = !!result.connection?.has_key && !!result.connection.model;
        setSavedModel(ready ? result.connection!.model : null);
        setModelStatus(ready ? 'ready' : 'missing');
      }).catch(() => { if (active) setModelStatus('error'); });
    };
    refresh();
    const settingsChanged = () => { setError(''); refresh(); };
    window.addEventListener('synthia-model-settings', settingsChanged);
    return () => { active = false; window.removeEventListener('synthia-model-settings', settingsChanged); };
  }, []);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [isFocused, setIsFocused] = useState(false);
  const [error, setError] = useState('');
  const [hasSession, setHasSession] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);

  // Restore draft from sessionStorage if available
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(DRAFT_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.topic) setTopic(parsed.topic);
        if (parsed.researchType) setResearchType(parsed.researchType);
        if (parsed.researchDepth) setResearchDepth(parsed.researchDepth);
        if (parsed.reportLength) setReportLength(parsed.reportLength);
        if (parsed.citationStyle) setCitationStyle(parsed.citationStyle);
        if (parsed.taskLanguage) setTaskLanguage(parsed.taskLanguage);
        if (typeof parsed.requirePlanApproval === 'boolean') setRequirePlanApproval(parsed.requirePlanApproval);
      }
    } catch {}
  }, []);

  // Check auth session
  useEffect(() => {
    const has = api.auth.hasSession();
    setHasSession(has);
    if (has) {
      api.auth.me().then(setCurrentUser).catch(() => {});
    }
  }, []);

  // Save draft whenever user makes changes
  useEffect(() => {
    try {
      if (topic.trim() || researchType !== 'REVIEW' || showAdvanced) {
        sessionStorage.setItem(
          DRAFT_STORAGE_KEY,
          JSON.stringify({
            topic,
            researchType,
            researchDepth,
            reportLength,
            citationStyle,
            taskLanguage,
            requirePlanApproval,
          })
        );
      }
    } catch {}
  }, [topic, researchType, researchDepth, reportLength, citationStyle, taskLanguage, requirePlanApproval, showAdvanced]);

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
    if (isLoading) return;
    const question = topic.trim();
    if (question.length < 10) {
      setError(isEn ? 'Please enter a research question with at least 10 characters.' : 'Vui lòng nhập câu hỏi nghiên cứu dài ít nhất 10 ký tự.');
      return;
    }

    // Preserve draft if not logged in
    if (!api.auth.hasSession()) {
      try {
        sessionStorage.setItem(
          DRAFT_STORAGE_KEY,
          JSON.stringify({
            topic: question,
            researchType,
            researchDepth,
            reportLength,
            citationStyle,
            taskLanguage,
            requirePlanApproval,
          })
        );
      } catch {}
      router.push('/login?next=%2F');
      return;
    }

    setError('');
    setIsLoading(true);
    setUploadStatus(isEn ? 'Checking saved API connection...' : 'Đang kiểm tra kết nối API đã lưu...');

    try {
      // Recheck the server, not the possibly stale/loading summary on this page.
      let connection;
      let serverMode = false;
      try {
        const options = await api.tasks.modelConnectionOptions();
        serverMode = !!options.use_server_providers;
        setUseServerProviders(serverMode);
        if (serverMode && !options.server_provider_ready) throw new Error('Server provider is not configured');
        if (!serverMode) connection = (await api.settings.getModelConnection()).connection;
      } catch {
        setModelStatus('error');
        setError(isEn ? 'Unable to check your saved API connection. Try again; your question and files are preserved.' : 'Không kiểm tra được kết nối API đã lưu. Hãy thử lại; câu hỏi và file vẫn được giữ nguyên.');
        return;
      }
      if (!serverMode && (!connection?.has_key || !connection.model)) {
        setSavedModel(null);
        setModelStatus('missing');
        setError(isEn ? 'No default API/model is saved for this account. Choose API & model below, save the connection, then start research.' : 'Tài khoản này chưa có API/model mặc định. Chọn API & model bên dưới, lưu kết nối rồi bấm bắt đầu.');
        return;
      }
      setSavedModel(serverMode ? 'Provider (.env)' : connection!.model);
      setModelStatus('ready');
      setUploadStatus(isEn ? 'Creating research workspace...' : 'Đang khởi tạo không gian nghiên cứu...');
      const task = await api.tasks.create({
        use_saved_connection: !serverMode,
        title: question.slice(0, 255),
        research_question: question,
        research_type: researchType,
        research_depth: researchDepth,
        report_length: reportLength,
        citation_style: citationStyle,
        language: taskLanguage || 'en', // Default to English
        require_plan_approval: requirePlanApproval,
        max_sources: maxSources,
      });


      // Tải lên các file PDF riêng tư nếu có trước khi bắt đầu workflow
      if (pdfFiles.length > 0) {
        for (let i = 0; i < pdfFiles.length; i++) {
          setUploadStatus(
            isEn
              ? `Uploading custom document ${i + 1}/${pdfFiles.length}: ${pdfFiles[i].name}...`
              : `Đang tải lên tài liệu ${i + 1}/${pdfFiles.length}: ${pdfFiles[i].name}...`
          );
          await api.tasks.uploadPdf(task.id, pdfFiles[i]);
        }
      }

      setUploadStatus(isEn ? 'Starting multi-agent workflow...' : 'Đang kích hoạt chuỗi tác vụ AI...');
      await api.tasks.start(task.id);

      // Clear draft upon successful launch
      try {
        sessionStorage.removeItem(DRAFT_STORAGE_KEY);
      } catch {}

      router.push(`/research/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : (isEn ? 'Unable to start research. Please try again.' : 'Không thể bắt đầu nghiên cứu. Vui lòng thử lại.'));
      setIsLoading(false);
      setUploadStatus('');
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
              <Button variant="outline" onClick={() => router.push('/settings')} className="text-xs h-8">Settings</Button>
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

            {/* Main Prompt Input Box */}
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
                  className="w-full resize-none border-0 bg-transparent py-2.5 text-sm sm:text-base text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-0 min-h-[85px]"
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
                        ? (isEn ? 'Computational Empirical' : 'Thực nghiệm tính toán')
                        : (isEn ? 'Fieldwork' : 'Thực nghiệm thực địa')}
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

            {/* 3 Real Research Types Cards (Prominently visible under the question prompt) */}
            <div className="mt-3.5 grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {/* Type 1: REVIEW */}
              <button
                type="button"
                onClick={() => setResearchType('REVIEW')}
                className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                  researchType === 'REVIEW'
                    ? 'border-zinc-900 bg-zinc-900 text-white shadow-xs'
                    : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50/70 text-zinc-900'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="flex items-center gap-1.5 font-semibold text-xs sm:text-[13px]">
                      <FileText size={15} className={researchType === 'REVIEW' ? 'text-zinc-200' : 'text-zinc-500'} />
                      <span>{isEn ? 'Literature Review' : 'Tổng quan tài liệu'}</span>
                    </span>
                    {researchType === 'REVIEW' && <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />}
                  </div>
                  <p className={`text-xs leading-relaxed ${researchType === 'REVIEW' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                    {isEn
                      ? 'Synthesizes published literature, compares findings, and structures a review manuscript.'
                      : 'Tổng quan tài liệu học thuật, đối chiếu chứng cứ và soạn thảo bài báo tổng quan lý thuyết.'}
                  </p>
                </div>
              </button>

              {/* Type 2: COMPUTATIONAL */}
              <button
                type="button"
                onClick={() => setResearchType('EMPIRICAL_COMPUTATIONAL')}
                className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                  researchType === 'EMPIRICAL_COMPUTATIONAL'
                    ? 'border-zinc-900 bg-zinc-900 text-white shadow-xs'
                    : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50/70 text-zinc-900'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="flex items-center gap-1.5 font-semibold text-xs sm:text-[13px]">
                      <Cpu size={15} className={researchType === 'EMPIRICAL_COMPUTATIONAL' ? 'text-purple-300' : 'text-purple-600'} />
                      <span>{isEn ? 'Computational Empirical' : 'Thực nghiệm tính toán'}</span>
                    </span>
                    {researchType === 'EMPIRICAL_COMPUTATIONAL' && <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />}
                  </div>
                  <p className={`text-xs leading-relaxed ${researchType === 'EMPIRICAL_COMPUTATIONAL' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                    {isEn
                      ? 'Executes automated baseline algorithms, statistical benchmarking, and reproducible routines.'
                      : 'Chạy quy trình tính toán tự động, mô hình baseline và đối sánh thực nghiệm kiểm chứng.'}
                  </p>
                </div>
              </button>

              {/* Type 3: FIELDWORK */}
              <button
                type="button"
                onClick={() => setResearchType('EMPIRICAL_HUMAN')}
                className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                  researchType === 'EMPIRICAL_HUMAN'
                    ? 'border-zinc-900 bg-zinc-900 text-white shadow-xs'
                    : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50/70 text-zinc-900'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="flex items-center gap-1.5 font-semibold text-xs sm:text-[13px]">
                      <FlaskConical size={15} className={researchType === 'EMPIRICAL_HUMAN' ? 'text-emerald-300' : 'text-emerald-600'} />
                      <span>{isEn ? 'Fieldwork / User Data' : 'Thực nghiệm thực địa'}</span>
                    </span>
                    {researchType === 'EMPIRICAL_HUMAN' && <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />}
                  </div>
                  <p className={`text-xs leading-relaxed ${researchType === 'EMPIRICAL_HUMAN' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                    {isEn
                      ? 'Formulates experimental protocol, then pauses for your real-world survey or sample dataset.'
                      : 'Thiết lập đề cương phương pháp, sau đó tạm dừng chờ nạp tập số liệu thực địa thực tế.'}
                  </p>
                </div>
              </button>
            </div>

            {/* Uploading Status Banner */}
            {isLoading && uploadStatus && (
              <div className="mt-3 flex items-center justify-center gap-2.5 text-xs text-blue-700 bg-blue-50/90 border border-blue-200 rounded-xl p-3 animate-pulse">
                <div className="w-3.5 h-3.5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin shrink-0" />
                <span className="font-medium">{uploadStatus}</span>
              </div>
            )}

            {/* Advanced Options Drawer */}
            {showAdvanced && (
              <div className="mt-3 bg-white rounded-xl border border-zinc-200 p-5 shadow-xs space-y-5 animate-in fade-in duration-150 z-10 relative">
                <div>
                  <h3 className="font-semibold text-sm text-zinc-900">
                    {isEn ? 'Research Configuration' : 'Tùy chọn cấu hình nghiên cứu'}
                  </h3>
                </div>

                {/* 1. Research Depth (Cards) */}
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-200 p-3 text-sm">
                  <span>{savedModel || (isEn ? 'Choose an API connection in Settings' : 'Chọn kết nối API trong Settings')}</span>
                  {!useServerProviders && <button type="button" className="font-medium underline" onClick={()=>setShowModelSettings(true)}>API & model</button>}
                </div>
                <label className="block space-y-1 text-xs font-medium text-zinc-700">
                  <span>{isEn ? 'Maximum sources to collect' : 'Số nguồn tối đa cần thu thập'}</span>
                  <input type="number" min={3} max={30} required value={maxSources}
                    onChange={event => setMaxSources(Number(event.target.value))}
                    className="block w-28 rounded-lg border border-zinc-200 p-2 text-sm" />
                  <span className="block font-normal text-zinc-500">{isEn
                    ? '3–30. Only relevant sources supporting the manuscript are cited; more sources may take longer.'
                    : '3–30. Chỉ trích dẫn nguồn phù hợp có hỗ trợ nội dung; tìm nhiều nguồn có thể lâu hơn.'}</span>
                </label>
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

                {/* Report Output Language Configuration */}
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

          {hasSession && <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-zinc-600">
            <span>{modelStatus === 'loading' ? (isEn ? 'Loading API configuration…' : 'Đang tải cấu hình API…')
              : modelStatus === 'error' ? (isEn ? 'API configuration could not be checked' : 'Chưa kiểm tra được cấu hình API')
                : savedModel || (isEn ? 'No default API/model saved' : 'Chưa có API/model mặc định')}</span>
            {!useServerProviders && <button type="button" onClick={() => setShowModelSettings(true)} className="font-medium underline">API & model</button>}
          </div>}

          {showModelSettings && <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 p-4">
            <section role="dialog" aria-modal="true" aria-labelledby="research-api-settings-title" className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
              <div className="mb-5 flex items-center justify-between gap-3">
                <h2 id="research-api-settings-title" className="font-semibold">API & model</h2>
                <button type="button" onClick={() => setShowModelSettings(false)} aria-label={isEn ? 'Close API settings' : 'Đóng cài đặt API'} className="rounded-lg p-2 hover:bg-zinc-100"><X size={18} /></button>
              </div>
              <ModelSettingsPanel isEn={isEn} />
            </section>
          </div>}

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
