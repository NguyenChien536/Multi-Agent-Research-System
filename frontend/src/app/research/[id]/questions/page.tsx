'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { BookOpen, ExternalLink, MessageCircle, Send } from 'lucide-react';
import { api, APIError } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';
import { useMonitorPoll } from '@/lib/use-monitor-poll';
import { PollStatus, formatTime } from '@/components/monitoring/MonitorUI';
import { questionErrorMessage, questionStatusLabel, safeSourceUrl } from '@/lib/report-questions';
import type { ReportVersionMetadata } from '@/types/report-questions';

function QuestionWorkspace({ taskId, version, setBusy }: {
  taskId: string; version: ReportVersionMetadata; setBusy: (value: boolean) => void;
}) {
  const { language } = useLanguage();
  const isEn = language === 'en';

  const [offset, setOffset] = useState(0);
  const [text, setText] = useState('');
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<{ request_id: string; question: string } | null>(null);
  const active = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const load = useCallback((signal: AbortSignal) => api.tasks.getQuestionHistory(taskId, version.version_number, offset, signal), [taskId, version.version_number, offset]);
  const history = useMonitorPoll(load, 5000);
  const data = history.data?.report_version_id === version.version_id ? history.data : null;
  const running = data?.items.some(item => item.status === 'RUNNING');

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; controller.current?.abort(); };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const question = text.trim();
    if (question.length < 3 || posting) return;
    if (request.current?.question !== question) request.current = { request_id: crypto.randomUUID(), question };
    controller.current = new AbortController();
    const timeout = setTimeout(() => controller.current?.abort(), 55000);
    setPosting(true); setBusy(true); setError('');
    try {
      await api.tasks.askQuestion(taskId, version.version_number, request.current, controller.current.signal);
      if (active.current) {
        request.current = null; setText(''); setOffset(0); history.refresh();
      }
    } catch (reason) {
      if (active.current) {
        const status = reason instanceof APIError ? reason.status : 0;
        setError(
          status === 409
            ? (isEn
                ? 'Task is not ready or currently answering another question. Check status before asking again.'
                : 'Bài chưa sẵn sàng hoặc đang trả lời câu hỏi khác. Kiểm tra tiến độ và lịch sử trước khi hỏi tiếp.')
            : status === 429
            ? (isEn
                ? 'Reached 50 questions limit for this task. You can still browse history.'
                : 'Đã đạt giới hạn 50 câu hỏi của bài. Bạn vẫn có thể xem lịch sử.')
            : (isEn
                ? 'No response received. The question might be saved; check history or retry.'
                : 'Chưa nhận được phản hồi. Câu hỏi có thể đã được lưu; xem lịch sử hoặc gửi lại nguyên câu hỏi để tránh tạo bản trùng.')
        );
        history.refresh();
      }
    } finally {
      clearTimeout(timeout);
      if (active.current) { setPosting(false); setBusy(false); }
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
        <label htmlFor="report-question" className="font-semibold text-zinc-900 text-sm sm:text-base">
          {isEn
            ? `What would you like to explore in version ${version.version_number}?`
            : `Bạn muốn hiểu thêm điều gì trong phiên bản ${version.version_number}?`}
        </label>
        <textarea
          id="report-question"
          value={text}
          disabled={posting}
          onChange={event => setText(event.target.value)}
          maxLength={2000}
          rows={3}
          placeholder={isEn ? "E.g. Which empirical evidence supports the primary hypothesis?" : "Ví dụ: Những nguồn nào hỗ trợ kết luận chính của bài?"}
          className="mt-3 block w-full resize-y rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-sm outline-none focus:border-zinc-900 focus:ring-1 focus:ring-zinc-900 disabled:opacity-60"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-zinc-600 font-medium">
            {text.length}/2000 {isEn ? 'chars · Max 50 questions per project' : 'ký tự · Tối đa 50 câu hỏi mỗi bài'}
          </span>
          <button
            disabled={posting || running || text.trim().length < 3}
            className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-40 transition-colors shadow-2xs cursor-pointer"
          >
            <Send size={15} />
            {posting
              ? (isEn ? 'Awaiting answer…' : 'Đang chờ câu trả lời…')
              : (isEn ? 'Submit Question' : 'Gửi câu hỏi')}
          </button>
        </div>
        {running && (
          <p role="status" className="mt-3 text-sm text-blue-700">
            {isEn
              ? 'A question for this version is currently being processed. History will refresh automatically.'
              : 'Một câu hỏi của phiên bản này đang được xử lý. Lịch sử sẽ tự cập nhật.'}
          </p>
        )}
        {posting && (
          <p role="status" className="mt-3 text-xs text-zinc-500">
            {isEn
              ? 'Questions are recorded before invoking LLM. Maximum response time ~40 seconds.'
              : 'Câu hỏi được lưu trước khi gọi AI. Thời gian xử lý tối đa khoảng 40 giây; tải lại trang để xem trạng thái nếu mất kết nối.'}
          </p>
        )}
        {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">{error}</p>}
      </form>

      <PollStatus error={history.error} lastSuccess={history.lastSuccess} refresh={history.refresh} />

      <section aria-label={isEn ? "Q&A History" : "Lịch sử hỏi đáp"} className="space-y-4">
        <h2 className="flex items-center gap-2 font-semibold text-base text-zinc-900">
          <MessageCircle size={18} />
          {isEn ? `Version ${version.version_number} Q&A History` : `Lịch sử phiên bản ${version.version_number}`}
        </h2>

        {!data && history.loading && (
          <p role="status" className="text-sm text-zinc-500">{isEn ? 'Loading history…' : 'Đang tải lịch sử…'}</p>
        )}

        {data?.total === 0 && (
          <div className="rounded-2xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500">
            {isEn
              ? 'No questions recorded for this version yet. Ask a specific question about findings, data, or citations.'
              : 'Chưa có câu hỏi cho phiên bản này. Hãy bắt đầu bằng một câu hỏi cụ thể về nội dung hoặc bằng chứng.'}
          </div>
        )}

        {data?.items.map(item => (
          <article key={item.id} className="overflow-hidden rounded-2xl border border-zinc-200 bg-white">
            <div className="border-b border-zinc-100 bg-zinc-50/60 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
                <time>{formatTime(item.created_at, language)}</time>
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-zinc-100 text-zinc-800 border border-zinc-200 text-xs font-medium">
                  <span className={`w-1.5 h-1.5 rounded-full ${item.status === 'ANSWERED' ? 'bg-emerald-600' : 'bg-amber-600'}`} />
                  {questionStatusLabel(item.status, language)}
                </span>
              </div>
              <h3 className="mt-3 whitespace-pre-wrap break-words font-semibold text-zinc-900 text-sm sm:text-base">{item.question}</h3>
            </div>
            <div className="space-y-4 p-5">
              {item.answer && <p className="whitespace-pre-wrap break-words text-sm leading-7 text-zinc-800">{item.answer}</p>}
              {item.error_code && (
                <p className="text-sm leading-6 text-red-700 bg-red-50 p-3 rounded-lg border border-red-200">
                  {questionErrorMessage(item.error_code, language)}
                </p>
              )}
              {item.status === 'RUNNING' && (
                <p className="text-sm text-blue-700">
                  {isEn ? 'Cross-referencing question against saved evidence chunks…' : 'Đang đối chiếu câu hỏi với các đoạn nguồn đã lưu…'}
                </p>
              )}
              {item.context_truncated && (
                <p className="text-xs leading-5 text-zinc-600 font-medium">
                  {isEn
                    ? 'Lengthy context was sampled for processing. Answer may not encompass every secondary paragraph.'
                    : 'Nội dung dài được chọn lọc trong phạm vi xử lý. Câu trả lời có thể chưa bao quát toàn bộ tài liệu.'}
                </p>
              )}
              {item.references.length > 0 && (
                <div className="space-y-3 border-t border-zinc-100 pt-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                    {isEn ? 'Cited Evidence Excerpts' : 'Đoạn nguồn được trích dẫn'}
                  </h4>
                  {item.references.map((ref, index) => (
                    <div key={ref.citation_id} className="rounded-xl border border-zinc-200/70 bg-zinc-50 p-4">
                      <p className="flex items-center gap-2 text-sm font-medium">
                        {safeSourceUrl(ref.source_url) ? (
                          <a
                            href={safeSourceUrl(ref.source_url)!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 break-all text-blue-700 hover:underline"
                          >
                            {index + 1}. {ref.source_title || (isEn ? 'Verified Source' : 'Nguồn đã lưu')}
                            <ExternalLink size={13} className="shrink-0" />
                          </a>
                        ) : (
                          <span>{index + 1}. {ref.source_title || (isEn ? 'Custom Uploaded Document' : 'Tài liệu riêng đã tải lên')}</span>
                        )}
                      </p>
                      <blockquote className="mt-3 whitespace-pre-wrap break-words border-l-2 border-zinc-300 pl-3 text-sm leading-6 text-zinc-600">
                        {ref.quote}
                      </blockquote>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </article>
        ))}

        {data && data.total > 20 && (
          <div className="flex items-center justify-between text-sm pt-2">
            <button
              disabled={!offset}
              onClick={() => setOffset(value => Math.max(0, value - 20))}
              className="rounded-lg border border-zinc-200 px-3 py-2 disabled:opacity-40 text-xs font-medium hover:bg-zinc-50 cursor-pointer"
            >
              {isEn ? 'Newer' : 'Mới hơn'}
            </button>
            <span className="text-xs text-zinc-500">
              {offset + 1}–{Math.min(offset + 20, data.total)} / {data.total}
            </span>
            <button
              disabled={offset + 20 >= data.total}
              onClick={() => setOffset(value => value + 20)}
              className="rounded-lg border border-zinc-200 px-3 py-2 disabled:opacity-40 text-xs font-medium hover:bg-zinc-50 cursor-pointer"
            >
              {isEn ? 'Older' : 'Cũ hơn'}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

function ArticleQuestions({ id }: { id: string }) {
  const { language } = useLanguage();
  const isEn = language === 'en';

  const [versions, setVersions] = useState<ReportVersionMetadata[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [versionRefresh, setVersionRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    let active = true;
    setVersions([]); setSelected(''); setError(''); setBusy(false);
    api.tasks.getReportVersions(id, controller.signal).then(values => {
      if (active) {
        setVersions(values); setSelected(values[0]?.version_id || '');
        if (!values.length) {
          setError(isEn ? 'This project has no saved report drafts yet.' : 'Bài chưa có phiên bản bản thảo được lưu.');
        }
      }
    }).catch(() => {
      if (active) {
        setError(isEn ? 'Unable to load report versions. A saved draft is required to use Q&A.' : 'Chưa tải được phiên bản bài báo. Bài cần có bản thảo đã lưu để sử dụng hỏi đáp.');
      }
    }).finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [id, versionRefresh, isEn]);

  const version = versions.find(item => item.version_id === selected);

  return (
    <main className="h-full overflow-y-auto bg-zinc-50 px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <header>
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
            {isEn ? 'Grounded Q&A' : 'Hỏi đáp có nguồn'}
          </p>
          <h1 className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-900">
            {isEn ? 'Understand Your Research Paper' : 'Hiểu rõ bài nghiên cứu'}
          </h1>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            {isEn
              ? 'Answers are grounded in saved evidence and source excerpts for your selected version. Verify sources for critical decisions.'
              : 'Câu trả lời dựa trên các đoạn nguồn được lưu cho phiên bản bạn chọn và sử dụng ngân sách AI còn lại của bài. Bạn nên đọc lại nguồn để đánh giá nội dung trước khi sử dụng.'}
          </p>
        </header>

        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-zinc-200 bg-white p-4">
          <label className="text-sm font-medium text-zinc-800 flex items-center">
            {isEn ? 'Version' : 'Phiên bản'}
            <select
              aria-label={isEn ? "Select report version" : "Chọn phiên bản bài báo"}
              disabled={busy || !versions.length}
              value={selected}
              onChange={event => setSelected(event.target.value)}
              className="ml-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs sm:text-sm font-medium focus:outline-none focus:ring-1 focus:ring-zinc-900"
            >
              {versions.map(item => (
                <option key={item.version_id} value={item.version_id}>
                  v{item.version_number} — {item.title}
                </option>
              ))}
            </select>
          </label>
          <Link href={`/research/${id}`} className="inline-flex items-center gap-2 text-sm font-medium text-zinc-700 hover:text-zinc-900">
            <BookOpen size={15} />
            {isEn ? 'Workspace · Latest Version' : 'Workspace · bản mới nhất'}
          </Link>
        </div>

        {version && (
          <details key={version.version_id} className="rounded-xl border border-zinc-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-semibold text-zinc-900 hover:text-zinc-700">
              {isEn ? `Inspect version ${version.version_number} content` : `Đối chiếu nội dung phiên bản ${version.version_number}`}
            </summary>
            <p className="mt-3 text-xs text-zinc-600 font-medium">
              {isEn ? 'Saved Markdown draft' : 'Bản Markdown đã lưu'} · {formatTime(version.created_at, language)}
            </p>
            <div className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-50 p-4 text-sm leading-7 text-zinc-700 border border-zinc-200">
              {version.content_markdown}
            </div>
          </details>
        )}

        {error && (
          <div role="alert" className="rounded-xl bg-amber-50 border border-amber-200 p-4 text-sm text-amber-900">
            <p>{error}</p>
            <button
              onClick={() => setVersionRefresh(value => value + 1)}
              className="mt-3 rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-medium hover:bg-amber-100 cursor-pointer"
            >
              {isEn ? 'Retry Loading' : 'Thử tải lại'}
            </button>
          </div>
        )}

        {!error && !version && (
          <p role="status" className="text-sm text-zinc-500">
            {isEn ? 'Loading versions…' : 'Đang tải các phiên bản…'}
          </p>
        )}

        {version && <QuestionWorkspace key={`${id}:${version.version_id}`} taskId={id} version={version} setBusy={setBusy} />}
      </div>
    </main>
  );
}

export default function ReportQuestionsPage() {
  const { id } = useParams<{ id: string }>();
  return <ArticleQuestions key={id} id={id} />;
}
