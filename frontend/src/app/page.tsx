'use client';

import { useState, useEffect, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { 
  Sparkles, FileText, Search, ArrowRight, Settings2, 
  ShieldCheck, ChevronDown, ChevronUp, LayoutDashboard, LogOut,
  Zap, Compass, Microscope
} from 'lucide-react';
import { api } from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState('');
  const [researchDepth, setResearchDepth] = useState<'SHALLOW' | 'STANDARD' | 'DEEP'>('STANDARD');
  const [reportLength, setReportLength] = useState<'SHORT' | 'MEDIUM' | 'LONG'>('MEDIUM');
  const [citationStyle, setCitationStyle] = useState<'IEEE' | 'APA' | 'HARVARD'>('IEEE');
  const [requirePlanApproval, setRequirePlanApproval] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [error, setError] = useState('');
  const [hasSession, setHasSession] = useState(false);

  useEffect(() => {
    setHasSession(api.auth.hasSession());
  }, []);

  const handleStartResearch = async (e: FormEvent) => {
    e.preventDefault();
    const question = topic.trim();
    if (question.length < 10) {
      setError('Vui lòng nhập câu hỏi nghiên cứu dài ít nhất 10 ký tự.');
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
        research_depth: researchDepth,
        report_length: reportLength,
        citation_style: citationStyle,
        language: 'vi',
        require_plan_approval: requirePlanApproval,
      });
      await api.tasks.start(task.id);
      router.push(`/research/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu nghiên cứu. Vui lòng thử lại.');
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
      <header className="w-full px-6 py-4 flex justify-between items-center z-20 border-b border-zinc-100 bg-white/70 backdrop-blur-md">
        <div className="flex items-center gap-2.5 font-bold text-xl tracking-tight">
          <div className="w-8 h-8 rounded-xl bg-zinc-900 text-white flex items-center justify-center text-sm shadow-md font-sans">S</div>
          <span>Synthia</span>
          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 border border-zinc-200">ATI</span>
        </div>

        {/* Clean, Non-redundant Navbar */}
        <div className="flex items-center gap-2">
          {hasSession ? (
            <>
              <Button variant="outline" onClick={() => router.push('/dashboard')}>
                <LayoutDashboard size={15} className="mr-1.5 text-zinc-600" /> Dashboard
              </Button>
              <Button variant="ghost" onClick={handleLogout} title="Đăng xuất khỏi hệ thống">
                <LogOut size={15} className="mr-1 text-zinc-500" /> Đăng xuất
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={() => router.push('/login')}>
              Đăng nhập / Đăng ký
            </Button>
          )}
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 z-10 max-w-4xl mx-auto w-full">
        <div className="w-full flex flex-col items-center gap-7 text-center animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="flex flex-col items-center gap-3">
            <h1 className="text-3xl md:text-5xl font-bold tracking-tight text-zinc-900 bg-clip-text text-transparent bg-gradient-to-br from-zinc-900 to-zinc-600">
              Bạn muốn nghiên cứu gì hôm nay?
            </h1>
            <p className="text-zinc-500 max-w-xl text-sm md:text-base leading-relaxed">
              Hệ thống đa tác tử AI (Multi-Agent) tự động tìm kiếm, chắt lọc bằng chứng, đối chiếu đa chiều và soạn thảo bài báo khoa học có trích dẫn minh bạch.
            </p>
          </div>

          <form onSubmit={handleStartResearch} className="w-full relative text-left">
            {/* Background focus blur - MUST have pointer-events-none so it never blocks clicks */}
            <div className={`absolute inset-0 bg-zinc-900/5 rounded-3xl blur-xl transition-opacity duration-500 pointer-events-none -z-10 ${isFocused ? 'opacity-100' : 'opacity-0'}`} />

            <div className="relative bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-zinc-200 p-3 transition-all duration-300 focus-within:shadow-[0_8px_30px_rgb(0,0,0,0.08)] focus-within:border-zinc-300 flex flex-col gap-2 z-10">
              <div className="flex items-start px-3 pt-2">
                <Search className="text-zinc-400 shrink-0 mr-3 mt-3.5" size={22} />
                <textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Nhập câu hỏi hoặc chủ đề nghiên cứu (VD: Phân tích ảnh hưởng của trí tuệ nhân tạo đối với an ninh phần mềm...)"
                  className="w-full resize-none border-0 bg-transparent py-3 text-base md:text-lg text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-0 min-h-[90px]"
                  disabled={isLoading}
                  rows={2}
                />
              </div>

              {/* Bottom bar of prompt box */}
              <div className="flex flex-wrap items-center justify-between border-t border-zinc-100 px-3 py-2.5 bg-zinc-50/60 -mx-3 -mb-3 rounded-b-3xl gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-zinc-200 text-xs font-medium text-zinc-700 shadow-sm">
                    <FileText size={13} className="text-zinc-500" />
                    <span>Tổng quan tài liệu</span>
                  </span>

                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-colors shadow-sm cursor-pointer ${showAdvanced ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100'}`}
                  >
                    <Settings2 size={13} className={showAdvanced ? 'text-white' : 'text-zinc-500'} />
                    <span>Cấu hình nghiên cứu</span>
                    {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || topic.trim().length < 10}
                  className="flex items-center gap-2 bg-zinc-900 text-white px-5 py-2.5 rounded-full font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm ml-auto cursor-pointer"
                >
                  {isLoading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>Bắt đầu nghiên cứu</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Advanced Options Drawer with Interactive Clickable Cards */}
            {showAdvanced && (
              <div className="mt-4 bg-white rounded-2xl border border-zinc-200 p-6 shadow-sm space-y-6 animate-in fade-in duration-200 z-10 relative">
                <div>
                  <h3 className="font-semibold text-sm text-zinc-900">Tùy chọn cấu hình nghiên cứu</h3>
                  <p className="text-xs text-zinc-500 mt-0.5">Tùy biến các tham số cho pipeline đa tác tử</p>
                </div>

                {/* 1. Research Depth (Cards) */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">Độ sâu nghiên cứu</label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <button
                      type="button"
                      onClick={() => setResearchDepth('SHALLOW')}
                      className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${researchDepth === 'SHALLOW' ? 'border-zinc-900 bg-zinc-900 text-white shadow-sm ring-2 ring-zinc-900/10' : 'border-zinc-200 bg-zinc-50 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center gap-2 font-semibold text-sm">
                        <Zap size={15} className={researchDepth === 'SHALLOW' ? 'text-amber-400' : 'text-zinc-600'} />
                        Nhanh (SHALLOW)
                      </div>
                      <div className={`text-xs mt-1 ${researchDepth === 'SHALLOW' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        1 vòng nghiên cứu, tối đa ~5 nguồn
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setResearchDepth('STANDARD')}
                      className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${researchDepth === 'STANDARD' ? 'border-zinc-900 bg-zinc-900 text-white shadow-sm ring-2 ring-zinc-900/10' : 'border-zinc-200 bg-zinc-50 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center gap-2 font-semibold text-sm">
                        <Compass size={15} className={researchDepth === 'STANDARD' ? 'text-blue-400' : 'text-zinc-600'} />
                        Tiêu chuẩn (STANDARD)
                      </div>
                      <div className={`text-xs mt-1 ${researchDepth === 'STANDARD' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        2 vòng nghiên cứu, tối đa ~10 nguồn
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setResearchDepth('DEEP')}
                      className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${researchDepth === 'DEEP' ? 'border-zinc-900 bg-zinc-900 text-white shadow-sm ring-2 ring-zinc-900/10' : 'border-zinc-200 bg-zinc-50 hover:bg-zinc-100 text-zinc-800'}`}
                    >
                      <div className="flex items-center gap-2 font-semibold text-sm">
                        <Microscope size={15} className={researchDepth === 'DEEP' ? 'text-emerald-400' : 'text-zinc-600'} />
                        Chuyên sâu (DEEP)
                      </div>
                      <div className={`text-xs mt-1 ${researchDepth === 'DEEP' ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        3 vòng nghiên cứu, tối đa ~20 nguồn
                      </div>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-2 border-t border-zinc-100">
                  {/* 2. Report Length */}
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">Độ dài bài báo</label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['SHORT', 'MEDIUM', 'LONG'] as const).map((len) => (
                        <button
                          key={len}
                          type="button"
                          onClick={() => setReportLength(len)}
                          className={`py-2 px-3 rounded-xl border text-xs font-medium text-center transition-all cursor-pointer ${reportLength === len ? 'bg-zinc-900 text-white border-zinc-900 font-semibold' : 'bg-zinc-50 border-zinc-200 text-zinc-700 hover:bg-zinc-100'}`}
                        >
                          {len === 'SHORT' ? 'Ngắn (~1.5k từ)' : len === 'MEDIUM' ? 'Vừa (~3k từ)' : 'Dài (~5k từ)'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 3. Citation Style */}
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">Kiểu trích dẫn</label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['IEEE', 'APA', 'HARVARD'] as const).map((style) => (
                        <button
                          key={style}
                          type="button"
                          onClick={() => setCitationStyle(style)}
                          className={`py-2 px-3 rounded-xl border text-xs font-medium text-center transition-all cursor-pointer ${citationStyle === style ? 'bg-zinc-900 text-white border-zinc-900 font-semibold' : 'bg-zinc-50 border-zinc-200 text-zinc-700 hover:bg-zinc-100'}`}
                        >
                          {style}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 4. HITL Plan Review */}
                <div className="border-t border-zinc-100 pt-4">
                  <button
                    type="button"
                    onClick={() => setRequirePlanApproval(!requirePlanApproval)}
                    className={`w-full p-4 rounded-xl border text-left flex items-start gap-3 transition-colors cursor-pointer ${requirePlanApproval ? 'bg-blue-50/60 border-blue-300 ring-1 ring-blue-300' : 'bg-zinc-50 border-zinc-200 hover:bg-zinc-100'}`}
                  >
                    <div className="mt-0.5">
                      <input
                        type="checkbox"
                        checked={requirePlanApproval}
                        onChange={() => {}} // Controlled by button click
                        className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-4 h-4 cursor-pointer"
                      />
                    </div>
                    <div>
                      <div className="font-semibold text-xs text-zinc-900 flex items-center gap-1.5">
                        <ShieldCheck size={14} className="text-blue-600" />
                        Chế độ có hướng dẫn (Human-in-the-Loop)
                      </div>
                      <div className="text-xs text-zinc-500 mt-0.5 leading-relaxed">
                        Agent lập kế hoạch sẽ tạm dừng sau giai đoạn Supervisor để bạn xem và duyệt đề cương nghiên cứu trước khi tìm kiếm nguồn.
                      </div>
                    </div>
                  </button>
                </div>
              </div>
            )}
          </form>

          {error && (
            <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-2.5 text-center">
              {error}
            </p>
          )}

          <div className="flex flex-wrap justify-center gap-3 text-xs font-medium text-zinc-500 mt-2">
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100/90 border border-zinc-200/60">
              <Sparkles size={13} className="text-amber-500" /> Tự động thu thập nguồn uy tín
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100/90 border border-zinc-200/60">
              <Sparkles size={13} className="text-blue-500" /> Phân tích chéo RAG và trích xuất bằng chứng
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100/90 border border-zinc-200/60">
              <Sparkles size={13} className="text-emerald-500" /> Trích dẫn có thể xác minh nguồn gốc
            </span>
          </div>
        </div>
      </main>

      {/* Decorative background blur elements with pointer-events-none */}
      <div className="fixed top-[20%] right-[10%] w-96 h-96 bg-blue-100/30 rounded-full blur-3xl -z-10 pointer-events-none" />
      <div className="fixed bottom-[10%] left-[5%] w-[30rem] h-[30rem] bg-amber-50/40 rounded-full blur-3xl -z-10 pointer-events-none" />
    </div>
  );
}
