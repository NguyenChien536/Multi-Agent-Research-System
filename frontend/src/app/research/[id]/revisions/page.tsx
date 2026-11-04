'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { BookOpen, RefreshCw, History, Send, ExternalLink, FileEdit, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';
import type { CitationResponse, ResearchReportResponse } from '@/types';
import { safeSourceUrl } from '@/lib/report-questions';
import type { ReportVersionMetadata } from '@/types/report-questions';
import { normalizeCitationLabel, revisionActive, revisionStatus, type ReportRevision } from '@/types/report-revisions';
import { PublicationArticle, PublicationExport } from '@/components/research/PublicationPaper';

export default function ManuscriptRevisions() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { language } = useLanguage();
  const isEn = language === 'en';

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
    setVersion(0);
    setVersions([]);
    setArticle(null);
    setInstructions('');
  }, [id]);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([api.tasks.getReportVersions(id, controller.signal), api.tasks.get(id)])
      .then(([list, task]) => {
        if (controller.signal.aborted) return;
        setVersions(list);
        setTaskStatus(task.status);
        if (!loaded.current && list.length) {
          const requested = Number(new URLSearchParams(window.location.search).get('version'));
          setVersion(list.some(item => item.version_number === requested) ? requested : list[0].version_number);
          loaded.current = true;
        }
      })
      .catch(err => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : (isEn ? 'Unable to load report versions.' : 'Không thể tải phiên bản.'));
        }
      });
    return () => controller.abort();
  }, [id, versionTick, isEn]);

  useEffect(() => {
    setInstructions('');
    request.current = null;
    setSelectedCitation(null);
  }, [id, version]);

  useEffect(() => {
    if (!version) return;
    const controller = new AbortController();
    setArticle(null);
    setCitations([]);
    setError('');
    void Promise.all([
      api.tasks.getReportVersion(id, version, controller.signal),
      api.tasks.getReportVersionCitations(id, version, controller.signal)
    ])
      .then(([result, refs]) => {
        if (!controller.signal.aborted) {
          setArticle(result);
          setCitations(refs);
        }
      })
      .catch(err => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : (isEn ? 'Unable to load manuscript draft.' : 'Không thể tải bản thảo.'));
        }
      });
    return () => controller.abort();
  }, [id, version, articleTick, isEn]);

  useEffect(() => {
    if (!version) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setHistory([]);

    const poll = async () => {
      try {
        const items = await api.tasks.getRevisionHistory(id, version, controller.signal);
        if (controller.signal.aborted) return;
        setHistory(items);
        setHistoryError('');
        for (const item of items) {
          if (!revisionActive(item) && !completed.current.has(item.id)) {
            completed.current.add(item.id);
            if (request.current?.request_id === item.request_id) request.current = null;
            setVersionTick(value => value + 1);
          }
        }
        if (items.some(revisionActive)) timer = setTimeout(() => void poll(), 3000);
      } catch (err) {
        if (!controller.signal.aborted) {
          setHistoryError(err instanceof Error ? err.message : (isEn ? 'Connection lost. Status may be delayed.' : 'Mất kết nối. Trạng thái có thể chưa cập nhật.'));
        }
      }
    };

    void poll();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [id, version, tick, isEn]);

  const active = history.some(revisionActive);
  const budgetBlocked = history.some(item => item.error_code === 'BUDGET_LIMIT');
  const latest = versions[0]?.version_number;
  const canSubmit = Boolean(
    article && version === latest && !active && !budgetBlocked &&
    ['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW', 'FAILED', 'CANCELLED'].includes(taskStatus)
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = instructions.trim();
    if (!canSubmit || busy || text.length < 10) return;
    if (!request.current || request.current.version !== version || request.current.instructions !== text) {
      request.current = { version, instructions: text, request_id: crypto.randomUUID() };
    }
    setBusy(true);
    setError('');
    try {
      const item = await api.tasks.reviseReport(id, version, { request_id: request.current.request_id, instructions: text });
      setHistory(rows => [item, ...rows.filter(row => row.id !== item.id)]);
      setTaskStatus('QUEUED');
    } catch (err) {
      setError(err instanceof Error ? err.message : (isEn ? 'Failed to submit revision. Retrying will use the same request token.' : 'Không gửi được yêu cầu. Thử lại sẽ dùng cùng mã yêu cầu.'));
    } finally {
      setBusy(false);
      setTick(value => value + 1);
    }
  };

  const openResult = async (versionId: string) => {
    setBusy(true);
    setError('');
    try {
      const list = versions.some(item => item.version_id === versionId) ? versions : await api.tasks.getReportVersions(id);
      const result = list.find(item => item.version_id === versionId);
      if (!result) throw new Error(isEn ? 'Result version is not available. Refresh to verify.' : 'Phiên bản kết quả không còn khả dụng. Bấm Cập nhật để kiểm tra lại.');
      setVersions(list);
      chooseVersion(result.version_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : (isEn ? 'Unable to open target version.' : 'Không thể mở phiên bản mới.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="h-full overflow-y-auto bg-zinc-50/60 p-4 sm:p-6 lg:p-8 text-zinc-900">
      <div className="w-full max-w-7xl mx-auto space-y-6">

        {/* Top Header Card */}
        <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white p-5 sm:p-6 rounded-xl border border-zinc-200 shadow-2xs">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-zinc-100 text-zinc-700 tracking-wider uppercase">
                {isEn ? "EDITORIAL REVISION & HISTORY" : "LỊCH SỬ CHỈNH SỬA & PHIÊN BẢN"}
              </span>
              <span className="text-zinc-300">•</span>
              <span className="text-xs text-zinc-600 font-medium">
                {isEn ? "Grounded Manuscript Iteration" : "Hiệu đính dựa trên bằng chứng"}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
              {isEn ? "Manuscript Revisions & History" : "Chỉnh sửa bản thảo và lịch sử phiên bản"}
            </h1>
            <p className="mt-0.5 max-w-3xl text-xs sm:text-sm text-zinc-600 font-normal leading-relaxed">
              {isEn
                ? "Refine phrasing, structure, and discussion based on grounded evidence of the active draft. Previous versions remain preserved. To alter raw data or computational routines, start a new research run."
                : "Sửa cách diễn đạt, bố cục và thảo luận dựa trên nguồn, số liệu của bản đang mở. Bản cũ luôn được giữ lại. Muốn đổi dữ liệu hoặc phương pháp, hãy tạo lượt nghiên cứu mới."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Link
              href={`/research/${id}`}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 text-xs font-medium text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 transition-colors shadow-2xs"
            >
              <BookOpen size={14} className="text-zinc-500" />
              <span>{isEn ? "Latest Paper" : "Bài mới nhất"}</span>
            </Link>
          </div>
        </header>

        {/* Version Picker Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs">
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="base-version" className="text-xs sm:text-sm font-semibold text-zinc-900 flex items-center gap-2">
              <History size={16} className="text-zinc-500" />
              <span>{isEn ? "Viewing Version:" : "Bản đang xem:"}</span>
            </label>
            <select
              id="base-version"
              disabled={busy}
              value={version}
              onChange={e => chooseVersion(Number(e.target.value))}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs sm:text-sm font-medium text-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900"
            >
              {!versions.length && <option value={0}>{isEn ? "No versions available" : "Chưa có phiên bản"}</option>}
              {versions.map(item => (
                <option key={item.version_id} value={item.version_number}>
                  v{item.version_number} — {item.review_status} — {new Date(item.created_at).toLocaleString(isEn ? 'en-US' : 'vi-VN')}
                </option>
              ))}
            </select>
            <button
              onClick={() => {
                setTick(value => value + 1);
                setVersionTick(value => value + 1);
                setArticleTick(value => value + 1);
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 cursor-pointer transition-colors shadow-2xs"
            >
              <RefreshCw size={13} className="text-zinc-500" />
              <span>{isEn ? "Refresh" : "Cập nhật"}</span>
            </button>
          </div>

          {article && (
            <div className="flex items-center gap-2 text-xs text-zinc-600 font-medium">
              <span>{isEn ? "Word count:" : "Số từ:"} <strong>{article.word_count.toLocaleString()}</strong></span>
              <span>•</span>
              <span className="px-2 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-zinc-800 text-[11px] font-semibold">
                {article.review_status}
              </span>
            </div>
          )}
        </div>

        {error && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs sm:text-sm font-medium text-red-800 flex items-center justify-between shadow-2xs">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-red-500 hover:text-red-700 font-bold ml-2">✕</button>
          </div>
        )}

        {/* 2-Column Content Grid: Manuscript & Evidence on Left, Revision Panel on Right */}
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">

          {/* Left Column: Full Version Manuscript & Grounded Citations */}
          <section className="min-w-0 rounded-2xl border border-zinc-200 bg-white p-5 sm:p-8 shadow-sm space-y-6" aria-label={isEn ? "Version manuscript content" : "Nội dung phiên bản đã lưu"}>
            {article ? (
              <>
                {/* Publication Export Toolbar */}
                <PublicationExport taskId={id} version={article.version_number} isEn={isEn} showRevisionLink={false} />

                <div className="border-b border-zinc-100 pb-4">
                  <h2 className="text-xl sm:text-2xl font-bold text-zinc-900 leading-snug">
                    {article.title}
                  </h2>
                  <p className="mt-1 text-xs text-zinc-500 font-mono">
                    DOI: 10.synthia/{id.slice(0, 8)} · v{article.version_number} ({article.review_status})
                  </p>
                </div>

                {/* Article Body */}
                <div className="pt-2">
                  <PublicationArticle
                    content={article.content_markdown}
                    metadata={article.review_metadata}
                    academicStyle={true}
                    onCitationClick={label => {
                      setSelectedCitation(normalizeCitationLabel(label));
                      document.getElementById('version-evidence')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}
                  />
                </div>

                {/* Version Evidence & Grounding Footnote Section */}
                <section id="version-evidence" className="mt-10 border-t border-zinc-200 pt-6" aria-label={isEn ? "Grounded evidence for active version" : "Bằng chứng của phiên bản đang xem"}>
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                    <h3 className="font-bold text-base text-zinc-900 flex items-center gap-2">
                      <CheckCircle2 size={16} className="text-blue-600" />
                      <span>
                        {isEn ? `Evidence & Grounding for v${article.version_number}` : `Nguồn & bằng chứng của v${article.version_number}`}
                        {selectedCitation ? ` · ${selectedCitation}` : ''}
                      </span>
                    </h3>
                    {selectedCitation && (
                      <button
                        onClick={() => setSelectedCitation(null)}
                        className="text-xs font-semibold text-blue-600 hover:underline cursor-pointer"
                      >
                        {isEn ? "Show all citations" : "Xem tất cả trích dẫn"}
                      </button>
                    )}
                  </div>

                  {selectedCitation && !citations.some(c => c.citation_label === selectedCitation) && (
                    <div role="status" className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 mb-3">
                      {isEn ? "Citation reference not found in current draft." : "Không tìm thấy trích dẫn này trong phiên bản đang xem. Hãy kiểm tra danh sách nguồn trước khi sử dụng."}
                    </div>
                  )}

                  <div className="space-y-3">
                    {(selectedCitation ? citations.filter(c => c.citation_label === selectedCitation) : citations).map(citation => {
                      const href = safeSourceUrl(citation.source_url);
                      return (
                        <div key={citation.id} className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/70 hover:bg-zinc-50 text-xs sm:text-sm space-y-2 transition-colors">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-zinc-900 flex items-center gap-1.5">
                              <span className="font-mono text-xs px-2 py-0.5 rounded bg-zinc-200 text-zinc-800">
                                {citation.citation_label}
                              </span>
                              <span>{citation.source_title || (isEn ? "Saved Literature Source" : "Nguồn đã lưu")}</span>
                            </span>
                            {href && (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline shrink-0"
                              >
                                <span>{isEn ? "Open Source" : "Mở nguồn"}</span>
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                          {citation.claim_text && (
                            <p className="text-zinc-700 leading-relaxed">
                              <strong>{isEn ? "Verified Claim: " : "Luận điểm đã lưu: "}</strong>
                              {citation.claim_text}
                            </p>
                          )}
                          {citation.chunk_content && (
                            <blockquote className="my-2 border-l-4 border-blue-400 pl-3 py-1 text-xs text-zinc-600 italic bg-white p-2 rounded-r-lg border border-zinc-200/60 leading-relaxed whitespace-pre-wrap">
                              {citation.chunk_content.slice(0, 1600)}
                            </blockquote>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              </>
            ) : (
              <div role="status" className="p-12 text-center text-zinc-500">
                {error
                  ? (isEn ? "Unable to load draft. Click Refresh to retry." : "Không thể tải bản thảo. Bấm Cập nhật để thử lại.")
                  : version
                  ? (isEn ? "Loading manuscript draft…" : "Đang tải bản thảo…")
                  : (isEn ? "Project does not have a saved draft yet." : "Bài chưa có bản thảo.")}
              </div>
            )}
          </section>

          {/* Right Column: Revision Request Form & History Timeline */}
          <aside className="space-y-6">

            {/* Form Card */}
            <form onSubmit={event => void submit(event)} className="rounded-2xl border border-zinc-200 bg-white p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-2 border-b border-zinc-100 pb-3">
                <FileEdit size={17} className="text-zinc-700" />
                <h3 className="font-bold text-base text-zinc-900">
                  {isEn ? `Revise Manuscript v${version || '—'}` : `Yêu cầu sửa v${version || '—'}`}
                </h3>
              </div>

              {version !== latest && latest && (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 leading-relaxed">
                  {isEn
                    ? `Viewing older version. Switch to latest v${latest} to request iterative revisions and avoid overwriting.`
                    : `Đây là bản cũ. Chọn v${latest} để sửa tiếp, tránh ghi đè thay đổi mới hơn.`}
                </div>
              )}

              {budgetBlocked && (
                <div role="status" className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 leading-relaxed">
                  {isEn
                    ? "Remaining project budget is insufficient for additional revisions. You can still inspect and export all saved versions."
                    : "Ngân sách còn lại không đủ để sửa tiếp. Hệ thống không tự tăng giới hạn; bạn vẫn có thể xem và xuất các phiên bản đã lưu."}
                </div>
              )}

              <div>
                <label htmlFor="revision-instructions" className="block text-xs sm:text-sm font-semibold text-zinc-800 mb-1.5">
                  {isEn ? "Revision Instructions:" : "Bạn muốn sửa điều gì?"}
                </label>
                <textarea
                  id="revision-instructions"
                  className="w-full min-h-36 rounded-xl border border-zinc-300 p-3 text-xs sm:text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-60 resize-y"
                  minLength={10}
                  maxLength={4000}
                  placeholder={
                    isEn
                      ? "E.g., Rewrite Introduction to clarify hypothesis; expand on experimental threats to validity in Discussion; keep empirical metrics intact."
                      : "Ví dụ: Viết lại Introduction rõ câu hỏi nghiên cứu hơn; giải thích giới hạn trong Discussion. Giữ nguyên số liệu thực nghiệm."
                  }
                  value={instructions}
                  disabled={!canSubmit || busy}
                  onChange={e => setInstructions(e.target.value)}
                  required
                />
                <div className="flex items-center justify-between text-xs text-zinc-500 mt-1">
                  <span>{instructions.length}/4000 {isEn ? "chars (min 10)" : "ký tự (tối thiểu 10)"}</span>
                  <span className="text-[11px] text-zinc-400">{isEn ? "Preserves grounding" : "Bảo đảm trích dẫn"}</span>
                </div>
              </div>

              <p className="text-[11px] text-zinc-500 leading-relaxed">
                {isEn
                  ? "Uses remaining task AI budget without inflating limits. Revised drafts undergo evidence checking and critique."
                  : "Dùng ngân sách còn lại của bài, không tự tăng giới hạn. Bản sửa vẫn phải qua kiểm tra chất lượng và trích dẫn."}
              </p>

              <button
                type="submit"
                disabled={!canSubmit || busy || instructions.trim().length < 10}
                className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-zinc-800 disabled:opacity-40 transition-colors shadow-2xs cursor-pointer"
              >
                <Send size={14} />
                <span>
                  {busy
                    ? (isEn ? "Submitting Request…" : "Đang gửi…")
                    : active
                    ? (isEn ? "Processing Revision…" : "Đang xử lý yêu cầu")
                    : (isEn ? "Generate Revised Draft" : "Tạo phiên bản đã chỉnh sửa")}
                </span>
              </button>
            </form>

            {/* History Timeline Card */}
            <section className="rounded-2xl border border-zinc-200 bg-white p-5 sm:p-6 shadow-sm space-y-4" aria-label={isEn ? "Revision history" : "Yêu cầu chỉnh sửa"}>
              <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
                <h3 className="font-bold text-sm sm:text-base text-zinc-900">
                  {isEn ? `Revision History (v${version || '—'})` : `20 yêu cầu gần nhất từ v${version || '—'}`}
                </h3>
                <span className="text-xs font-mono text-zinc-500">{history.length}</span>
              </div>

              {historyError && (
                <p role="alert" className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
                  {historyError} {isEn ? "Click Refresh to retry." : "Bấm Cập nhật để thử lại."}
                </p>
              )}

              {!history.length && !historyError && (
                <p className="text-xs text-zinc-500 py-4 text-center">
                  {isEn ? "No revisions requested for this version yet." : "Chưa có yêu cầu sửa từ phiên bản này."}
                </p>
              )}

              <ul className="space-y-4">
                {history.map(item => (
                  <li key={item.id} className="border-t border-zinc-100 pt-3 text-xs sm:text-sm space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${
                        item.status === 'COMPLETED'
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                          : item.status === 'RUNNING' || item.status === 'QUEUED'
                          ? 'bg-blue-50 text-blue-800 border-blue-200 animate-pulse'
                          : 'bg-zinc-100 text-zinc-700 border-zinc-200'
                      }`}>
                        {revisionStatus(item)}
                      </span>
                      <time className="text-[11px] text-zinc-500 font-mono">
                        {new Date(item.created_at).toLocaleString(isEn ? 'en-US' : 'vi-VN')}
                      </time>
                    </div>

                    <p className="text-zinc-700 leading-relaxed whitespace-pre-wrap break-words bg-zinc-50 p-2.5 rounded-lg border border-zinc-200/60 text-xs">
                      {item.instructions}
                    </p>

                    {item.result_version_id && (
                      <button
                        disabled={busy}
                        onClick={() => void openResult(item.result_version_id!)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:underline cursor-pointer disabled:opacity-50"
                      >
                        <span>{isEn ? "View Result Version →" : "Xem phiên bản mới →"}</span>
                        {item.status === 'NEEDS_REVIEW' && (
                          <span className="text-zinc-500 text-[11px] font-normal">
                            {isEn ? "(needs review)" : "(cần rà soát)"}
                          </span>
                        )}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </div>

      </div>
    </main>
  );
}
