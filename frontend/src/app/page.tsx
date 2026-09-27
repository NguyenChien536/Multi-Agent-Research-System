'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Input, Card } from '@/components/ui/Components';
import { api } from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStartResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (topic.trim().length < 10) {
      setError('Vui lòng nhập chủ đề dài hơn (ít nhất 10 ký tự) để AI hiểu rõ ngữ cảnh.');
      return;
    }

    setError('');
    setIsLoading(true);

    try {
      // 1. Khởi tạo task
      const task = await api.tasks.create({
        title: topic.substring(0, 50) + (topic.length > 50 ? '...' : ''),
        research_question: topic,
        research_depth: 'STANDARD',
        language: 'vi',
        require_plan_approval: false // MVP: Không dùng HITL vì backend chưa hỗ trợ api duyệt
      });

      // 2. Kích hoạt workflow Celery
      await api.tasks.start(task.id);

      // 3. Chuyển hướng sang trang chi tiết task
      router.push(`/research/${task.id}`);
    } catch (err: any) {
      setError(err.message || 'Có lỗi xảy ra khi khởi tạo task. Vui lòng kiểm tra kết nối API.');
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-zinc-50 text-zinc-900">
      <div className="w-full max-w-3xl flex flex-col items-center gap-8 text-center">

        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-zinc-900 text-white flex items-center justify-center font-bold text-xl shadow-lg">S</div>
          <h1 className="text-3xl md:text-5xl font-semibold tracking-tight text-zinc-900">
            Synthia
          </h1>
          <p className="text-zinc-500 max-w-xl text-sm md:text-base">
            Hệ thống nghiên cứu tự động chuyên sâu. Nhập câu hỏi nghiên cứu của bạn để AI tiến hành thu thập, phân tích và tổng hợp thông tin từ các nguồn uy tín.
          </p>
        </div>

        <Card className="w-full p-2 pl-4 pr-2 rounded-2xl shadow-sm bg-white border border-zinc-200">
          <form onSubmit={handleStartResearch} className="flex flex-col md:flex-row gap-2">
            <Input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="VD: Phân tích ảnh hưởng của trí tuệ nhân tạo đến ngành giáo dục..."
              className="border-0 shadow-none focus-visible:ring-0 text-base py-6 px-2 flex-1"
              disabled={isLoading}
            />
            <Button
              type="submit"
              className="py-6 px-8 rounded-xl shrink-0 font-semibold"
              isLoading={isLoading}
            >
              Nghiên cứu ngay
            </Button>
          </form>
        </Card>

        {error && (
          <p className="text-red-500 text-sm bg-red-50 px-4 py-2 rounded-lg border border-red-100">
            {error}
          </p>
        )}

        <div className="flex gap-4 text-xs text-zinc-400 font-medium">
          <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-zinc-400" /> Tự động thu thập nguồn</span>
          <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-zinc-400" /> RAG & Phân tích chéo</span>
          <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-zinc-400" /> Trích dẫn minh bạch</span>
        </div>
      </div>
    </main>
  );
}
