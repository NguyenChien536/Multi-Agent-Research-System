'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CitationResponse, ResearchReportResponse } from '@/types';
import { safeSourceUrl } from '@/lib/report-questions';
import type { ReportVersionMetadata } from '@/types/report-questions';
import { revisionActive, revisionStatus, type ReportRevision } from '@/types/report-revisions';
import { PublicationArticle, PublicationExport } from '@/components/research/PublicationPaper';

export default function ManuscriptRevisions() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [versions, setVersions] = useState<ReportVersionMetadata[]>([]);
  const [version, setVersion] = useState(0);
  const [article, setArticle] = useState<ResearchReportResponse | null>(null);
  const [citations, setCitations] = useState<CitationResponse[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<string | null>(null);
  const [history, setHistory] = useState<ReportRevision[]>([]);
  const [instructions, setInstructions] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [tick, setTick] = useState(0);
  const [versionTick, setVersionTick] = useState(0);
  const [articleTick, setArticleTick] = useState(0);
  const [taskStatus, setTaskStatus] = useState('');
  const request = useRef<{ version: number; instructions: string; request_id: string } | null>(null);
  const loaded = useRef(false);
  const completed = useRef(new Set<string>());
  const chooseVersion = (number: number) => {
    setVersion(number);
    router.replace(`/research/${id}/revisions?version=${number}`, { scroll: false });
  };

  useEffect(() => {
    loaded.current = false;
    completed.current.clear();
    request.current = null;
    setVersion(0); setVersions([]); setArticle(null); setInstructions('');
  }, [id]);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([api.tasks.getReportVersions(id, controller.signal), api.tasks.get(id)]).then(([list, task]) => {
      if (controller.signal.aborted) return;
      setVersions(list); setTaskStatus(task.status);
      if (!loaded.current && list.length) {
        const requested = Number(new URLSearchParams(window.location.search).get('version'));
        setVersion(list.some(item => item.version_number === requested) ? requested : list[0].version_number);
        loaded.current = true;
      }
    }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Không thể tải phiên bản.'); });
    return () => controller.abort();
  }, [id, versionTick]);

  useEffect(() => {
    setInstructions(''); request.current = null; setSelectedCitation(null);
  }, [id, version]);

  useEffect(() => {
    if (!version) return;
    const controller = new AbortController();
    setArticle(null); setCitations([]); setError('');
    void Promise.all([api.tasks.getReportVersion(id, version, controller.signal), api.tasks.getReportVersionCitations(id, version, controller.signal)]).then(([result, refs]) => {
      if (!controller.signal.aborted) { setArticle(result); setCitations(refs); }
    }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Không thể tải bản thảo.'); });
    return () => controller.abort();
  }, [id, version, articleTick]);

  useEffect(() => {
    if (!version) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setHistory([]);
    const poll = async () => {
      try {
        const items = await api.tasks.getRevisionHistory(id, version, controller.signal);
        if (controller.signal.aborted) return;
        setHistory(items); setHistoryError('');
        for (const item of items) {
          if (!revisionActive(item) && !completed.current.has(item.id)) {
            completed.current.add(item.id);
            if (request.current?.request_id === item.request_id) request.current = null;
            setVersionTick(value => value + 1);
          }
        }
        if (items.some(revisionActive)) timer = setTimeout(() => void poll(), 3000);
      } catch (err) {
        if (!controller.signal.aborted) setHistoryError(err instanceof Error ? err.message : 'Mất kết nối. Trạng thái có thể chưa cập nhật.');
      }
    };
    void poll();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [id, version, tick]);

  const active = history.some(revisionActive);
  const budgetBlocked = history.some(item => item.error_code === 'BUDGET_LIMIT');
  const latest = versions[0]?.version_number;
  const canSubmit = Boolean(article && version === latest && !active && !budgetBlocked && ['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW', 'FAILED', 'CANCELLED'].includes(taskStatus));
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = instructions.trim();
    if (!canSubmit || busy || text.length < 10) return;
    if (!request.current || request.current.version !== version || request.current.instructions !== text) {
      request.current = { version, instructions: text, request_id: crypto.randomUUID() };
    }
    setBusy(true); setError('');
    try {
      const item = await api.tasks.reviseReport(id, version, { request_id: request.current.request_id, instructions: text });
      setHistory(rows => [item, ...rows.filter(row => row.id !== item.id)]);
      setTaskStatus('QUEUED');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không gửi được yêu cầu. Thử lại sẽ dùng cùng mã yêu cầu.');
    } finally { setBusy(false); setTick(value => value + 1); }
  };

  const openResult = async (versionId: string) => {
    setBusy(true); setError('');
    try {
      const list = versions.some(item => item.version_id === versionId) ? versions : await api.tasks.getReportVersions(id);
      const result = list.find(item => item.version_id === versionId);
      if (!result) throw new Error('Phiên bản kết quả không còn khả dụng. Bấm Cập nhật để kiểm tra lại.');
      setVersions(list); chooseVersion(result.version_number);
    } catch (err) { setError(err instanceof Error ? err.message : 'Không thể mở phiên bản mới.'); }
    finally { setBusy(false); }
  };

  return <main className="mx-auto max-w-7xl p-4 md:p-8 text-zinc-900">
    <Link href={`/research/${id}`} className="text-sm underline">← Về bài nghiên cứu</Link>
    <h1 className="mt-5 text-2xl font-semibold">Chỉnh sửa bản thảo và lịch sử phiên bản</h1>
    <p className="mt-2 text-sm text-zinc-600">Sửa cách diễn đạt, bố cục và thảo luận dựa trên nguồn, số liệu của bản đang mở. Bản cũ luôn được giữ lại. Muốn đổi dữ liệu hoặc phương pháp, hãy tạo lượt nghiên cứu mới.</p>
    <div className="my-5 flex flex-wrap items-center gap-3">
      <label htmlFor="base-version" className="text-sm font-medium">Bản đang xem</label>
      <select id="base-version" className="rounded border bg-white p-2" disabled={busy} value={version} onChange={e => chooseVersion(Number(e.target.value))}>
        {!versions.length && <option value={0}>Chưa có phiên bản</option>}
        {versions.map(item => <option key={item.version_id} value={item.version_number}>v{item.version_number} — {item.review_status} — {new Date(item.created_at).toLocaleString('vi-VN')}</option>)}
      </select>
      <button className="rounded border px-3 py-2 text-sm" onClick={() => { setTick(value => value + 1); setVersionTick(value => value + 1); setArticleTick(value => value + 1); }}>Cập nhật</button>
    </div>
    {error && <p role="alert" className="my-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="min-w-0 rounded-xl border border-zinc-200 bg-white p-5 md:p-8" aria-label="Nội dung phiên bản đã lưu">
        {article ? <><PublicationExport taskId={id} version={article.version_number} isEn={false} showRevisionLink={false} />
          <p className="mb-5 text-xs text-zinc-500">v{article.version_number} · {article.review_status}. Đây là bản thảo để người nghiên cứu rà soát.</p>
          <PublicationArticle content={article.content_markdown} metadata={article.review_metadata} onCitationClick={label => {
            setSelectedCitation(label); document.getElementById('version-evidence')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }} />
          <section id="version-evidence" className="mt-8 border-t pt-5" aria-label="Bằng chứng của phiên bản đang xem">
            <h2 className="font-semibold">Nguồn và bằng chứng của v{article.version_number}{selectedCitation ? ` · ${selectedCitation}` : ''}</h2>
            {selectedCitation && <button className="mt-2 text-sm underline" onClick={() => setSelectedCitation(null)}>Xem các trích dẫn khác</button>}
            {(selectedCitation ? citations.filter(c => c.citation_label === selectedCitation) : citations).map(citation => {
              const href = safeSourceUrl(citation.source_url);
              return <div key={citation.id} className="mt-4 rounded border p-4 text-sm">
                <p className="font-medium">{citation.citation_label} {citation.source_title || 'Nguồn đã lưu'}</p>
                {citation.claim_text && <p className="mt-2">Luận điểm đã lưu: {citation.claim_text}</p>}
                {citation.chunk_content && <blockquote className="my-3 whitespace-pre-wrap border-l-2 pl-3 text-zinc-600">{citation.chunk_content.slice(0,1600)}</blockquote>}
                <p className="text-xs text-zinc-500">Đoạn nguồn có thể đã rút gọn; đối chiếu bản gốc khi sử dụng.</p>
                {href && <a href={href} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block underline">Mở nguồn</a>}
              </div>;
            })}
          </section>
        </> : <p role="status">{error ? 'Không thể tải bản thảo. Bấm Cập nhật để thử lại.' : version ? 'Đang tải bản thảo…' : 'Bài chưa có bản thảo.'}</p>}
      </section>
      <aside className="space-y-5">
        <form onSubmit={event => void submit(event)} className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">Yêu cầu sửa v{version || '—'}</h2>
          {version !== latest && latest && <p className="my-2 text-sm text-amber-800">Đây là bản cũ. Chọn v{latest} để sửa tiếp, tránh ghi đè thay đổi mới hơn.</p>}
          {budgetBlocked && <p role="status" className="my-2 text-sm text-amber-800">Ngân sách còn lại không đủ để sửa tiếp. Hệ thống không tự tăng giới hạn; bạn vẫn có thể xem và xuất các phiên bản đã lưu.</p>}
          <label htmlFor="revision-instructions" className="mt-4 block text-sm">Bạn muốn sửa điều gì?</label>
          <textarea id="revision-instructions" className="mt-2 min-h-40 w-full rounded border p-3 text-sm disabled:opacity-60" minLength={10} maxLength={4000}
            placeholder="Ví dụ: Viết lại Introduction rõ câu hỏi nghiên cứu hơn; giải thích giới hạn trong Discussion. Giữ nguyên số liệu thực nghiệm."
            value={instructions} disabled={!canSubmit || busy} onChange={e => setInstructions(e.target.value)} required />
          <p className="mt-2 text-xs text-zinc-500">Dùng ngân sách còn lại của bài, không tự tăng giới hạn. Bản sửa vẫn phải qua kiểm tra chất lượng và trích dẫn.</p>
          <button type="submit" disabled={!canSubmit || busy || instructions.trim().length < 10} className="mt-4 rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{busy ? 'Đang gửi…' : active ? 'Đang xử lý yêu cầu' : 'Tạo phiên bản đã chỉnh sửa'}</button>
        </form>
        <section className="rounded-xl border bg-white p-5" aria-label="Yêu cầu chỉnh sửa">
          <h2 className="font-semibold">20 yêu cầu gần nhất từ v{version || '—'}</h2>
          {historyError && <p role="alert" className="mt-2 text-sm text-red-700">{historyError} Bấm Cập nhật để thử lại.</p>}
          {!history.length && !historyError && <p className="mt-3 text-sm text-zinc-500">Chưa có yêu cầu sửa từ phiên bản này.</p>}
          <ul className="mt-3 space-y-4">{history.map(item => <li key={item.id} className="border-t pt-3 text-sm">
            <p role={revisionActive(item) ? 'status' : undefined} className="font-medium">{revisionStatus(item)}</p>
            <time className="text-xs text-zinc-500">{new Date(item.created_at).toLocaleString('vi-VN')}</time>
            <p className="mt-2 whitespace-pre-wrap break-words">{item.instructions}</p>
            {item.result_version_id && <button disabled={busy} className="mt-2 underline disabled:opacity-50" onClick={() => void openResult(item.result_version_id!)}>Xem phiên bản mới{item.status === 'NEEDS_REVIEW' ? ' (cần rà soát)' : ''}</button>}
          </li>)}</ul>
        </section>
      </aside>
    </div>
  </main>;
}
