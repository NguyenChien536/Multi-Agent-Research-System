'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Sparkles, FileText, Search, ArrowRight, Settings2, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';
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

  return (
    <div className="min-h-screen bg-[#fcfcfc] flex flex-col text-zinc-900 relative">
      {/* Header */}
      <header className="w-full px-6 py-5 flex justify-between items-center z-10">
        <div className="flex items-center gap-2.5 font-bold text-xl tracking-tight">
          <div className="w-8 h-8 rounded-xl bg-zinc-900 text-white flex items-center justify-center text-sm shadow-md font-sans">S</div>
          <span>Synthia</span>
          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 border border-zinc-200">ATI</span>
        </div>
        <div className="flex gap-3">
          <Button variant="ghost" onClick={() => router.push('/dashboard')}>Dashboard</Button>
          <Button variant="outline" onClick={() => router.push(api.auth.hasSession() ? '/dashboard' : '/login')}>
            {api.auth.hasSession() ? 'Không gian của bạn' : 'Đăng nhập'}
          </Button>
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

          <form onSubmit={handleStartResearch} className="w-full relative group text-left">
            <div className={`absolute inset-0 bg-zinc-900/5 rounded-3xl blur-xl transition-opacity duration-500 ${isFocused ? 'opacity-100' : 'opacity-0'}`} />

            <div className="relative bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-zinc-200 p-3 transition-all duration-300 focus-within:shadow-[0_8px_30px_rgb(0,0,0,0.08)] focus-within:border-zinc-300 flex flex-col gap-2">
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
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-zinc-200 text-xs font-medium text-zinc-700 hover:bg-zinc-100 transition-colors shadow-sm"
                  >
                    <Settings2 size={13} className="text-zinc-500" />
                    <span>Cấu hình nghiên cứu</span>
                    {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || topic.trim().length < 10}
                  className="flex items-center gap-2 bg-zinc-900 text-white px-5 py-2.5 rounded-full font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm ml-auto"
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

            {/* Advanced Options Drawer */}
            {showAdvanced && (
              <div className="mt-3 bg-white rounded-2xl border border-zinc-200 p-5 shadow-sm space-y-4 animate-in fade-in duration-200">
                <h3 className="font-semibold text-xs uppercase tracking-wider text-zinc-500">Tùy chọn nghiên cứu chuyên sâu</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  {/* Research Depth */}
                  <div>
                    <label className="block text-xs font-medium text-zinc-700 mb-1.5">Độ sâu nghiên cứu</label>
                    <select
                      value={researchDepth}
                      onChange={(e) => setResearchDepth(e.target.value as any)}
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-800 outline-none focus:border-zinc-900"
                    >
                      <option value="SHALLOW">Tổng quan nhanh (1 vòng, ~5 nguồn)</option>
                      <option value="STANDARD">Tiêu chuẩn (2 vòng, ~10 nguồn)</option>
                      <option value="DEEP">Chuyên sâu (3 vòng, ~20 nguồn)</option>
                    </select>
                  </div>

                  {/* Report Length */}
                  <div>
                    <label className="block text-xs font-medium text-zinc-700 mb-1.5">Độ dài bài báo</label>
                    <select
                      value={reportLength}
                      onChange={(e) => setReportLength(e.target.value as any)}
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-800 outline-none focus:border-zinc-900"
                    >
                      <option value="SHORT">Ngắn gọn (~1.500 từ)</option>
                      <option value="MEDIUM">Vừa phải (~3.000 từ)</option>
                      <option value="LONG">Chi tiết (~5.000 từ)</option>
                    </select>
                  </div>

                  {/* Citation Style */}
                  <div>
                    <label className="block text-xs font-medium text-zinc-700 mb-1.5">Kiểu trích dẫn</label>
                    <select
                      value={citationStyle}
                      onChange={(e) => setCitationStyle(e.target.value as any)}
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-800 outline-none focus:border-zinc-900"
                    >
                      <option value="IEEE">IEEE [1] (Kỹ thuật / CS)</option>
                      <option value="APA">APA (Tác giả, Năm)</option>
                      <option value="HARVARD">Harvard</option>
                    </select>
                  </div>
                </div>

                {/* HITL Plan Review */}
                <div className="border-t border-zinc-100 pt-3">
                  <label className="flex items-center gap-2.5 cursor-pointer text-xs font-medium text-zinc-700">
                    <input
                      type="checkbox"
                      checked={requirePlanApproval}
                      onChange={(e) => setRequirePlanApproval(e.target.checked)}
                      className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-4 h-4"
                    />
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck size={14} className="text-zinc-500" />
                      Yêu cầu dừng lại để người dùng xem và phê duyệt kế hoạch trước khi nghiên cứu (Human-in-the-Loop)
                    </span>
                  </label>
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

      {/* Decorative background blur elements */}
      <div className="fixed top-[20%] right-[10%] w-96 h-96 bg-blue-100/30 rounded-full blur-3xl -z-10 pointer-events-none" />
      <div className="fixed bottom-[10%] left-[5%] w-[30rem] h-[30rem] bg-amber-50/40 rounded-full blur-3xl -z-10 pointer-events-none" />
    </div>
  );
}
