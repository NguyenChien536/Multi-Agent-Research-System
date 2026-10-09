'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Sparkles, FileText, Search, ArrowRight } from 'lucide-react';
import { api } from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState('');
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
        research_depth: 'STANDARD',
        language: 'vi',
        require_plan_approval: false,
      });
      await api.tasks.start(task.id);
      router.push(`/research/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu nghiên cứu. Vui lòng thử lại.');
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#fcfcfc] overflow-hidden flex-col md:flex-row text-zinc-900 relative">
      {/* Absolute Header Links */}
      <div className="absolute top-0 left-0 right-0 p-6 flex justify-between items-center z-10">
        <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
          <div className="w-8 h-8 rounded-lg bg-zinc-900 text-white flex items-center justify-center text-sm shadow-md">S</div>
          Synthia
        </div>
        <div className="flex gap-4">
          <Button variant="ghost" onClick={() => router.push('/dashboard')}>Dashboard</Button>
          <Button variant="outline" onClick={() => router.push(api.auth.hasSession() ? '/dashboard' : '/login')}>Tài khoản</Button>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 z-10 relative mt-16 md:mt-0">
        <div className="w-full max-w-3xl flex flex-col items-center gap-8 text-center animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="flex flex-col items-center gap-5">
            <h1 className="text-4xl md:text-6xl font-semibold tracking-tight text-zinc-900 bg-clip-text text-transparent bg-gradient-to-br from-zinc-900 to-zinc-600">
              Bạn muốn nghiên cứu gì hôm nay?
            </h1>
            <p className="text-zinc-500 max-w-xl text-base md:text-lg">
              Hệ thống đa tác tử AI (Multi-Agent) tự động thu thập, phân tích và tổng hợp thông tin từ các nguồn uy tín.
            </p>
          </div>

          <form onSubmit={handleStartResearch} className="w-full relative group">
            <div className={`absolute inset-0 bg-zinc-900/5 rounded-3xl blur-xl transition-opacity duration-500 ${isFocused ? 'opacity-100' : 'opacity-0'}`} />

            <div className="relative bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-zinc-200/80 p-2 transition-all duration-300 focus-within:shadow-[0_8px_30px_rgb(0,0,0,0.08)] focus-within:border-zinc-300 flex flex-col gap-2 overflow-hidden">
              <div className="flex items-center px-4 pt-2">
                <Search className="text-zinc-400 shrink-0 mr-3" size={24} />
                <textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Nhập chủ đề nghiên cứu (VD: Phân tích ảnh hưởng của trí tuệ nhân tạo đến ngành giáo dục...)"
                  className="w-full resize-none border-0 bg-transparent py-3 text-lg md:text-xl text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-0 min-h-[80px]"
                  disabled={isLoading}
                  rows={2}
                />
              </div>

              <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3 bg-zinc-50/50 -mx-2 -mb-2 rounded-b-3xl mt-2">
                <div className="flex gap-2">
                  <span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-zinc-200 text-xs font-medium text-zinc-600">
                    <FileText size={14} />
                    <span>Tổng quan tài liệu</span>
                  </span>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || topic.trim().length < 10}
                  className="flex items-center gap-2 bg-zinc-900 text-white px-5 py-2.5 rounded-full font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                  {isLoading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>Nghiên cứu</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-2">{error}</p>}

          <div className="flex flex-wrap justify-center gap-4 text-xs font-medium text-zinc-500 mt-2">
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100/80"><Sparkles size={14} className="text-amber-500" /> Tự động thu thập nguồn</span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100/80"><Sparkles size={14} className="text-blue-500" /> Phân tích chéo RAG</span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100/80"><Sparkles size={14} className="text-emerald-500" /> Trích dẫn minh bạch</span>
          </div>
        </div>
      </div>

      {/* Decorative background elements */}
      <div className="fixed top-[20%] right-[10%] w-96 h-96 bg-blue-100/40 rounded-full blur-3xl -z-10 pointer-events-none" />
      <div className="fixed bottom-[10%] left-[5%] w-[30rem] h-[30rem] bg-amber-50/50 rounded-full blur-3xl -z-10 pointer-events-none" />
    </div>
  );
}
