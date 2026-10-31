'use client';

import { useState, type ComponentProps } from 'react';
import { api } from '@/lib/api';
import { MarkdownViewer } from '@/components/ui/MarkdownViewer';
import Link from 'next/link';
import { ExperimentBundleExport } from './ExperimentBundleExport';
type ViewerProps = ComponentProps<typeof MarkdownViewer> & { academicStyle?: boolean };

export function PublicationExport({ taskId, version, isEn, showRevisionLink = true }: { taskId: string; version?: number; isEn: boolean; showRevisionLink?: boolean }) {
  const [template, setTemplate] = useState<'IEEE_CONFERENCE' | 'ACM_SIGCONF'>('IEEE_CONFERENCE');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const download = async () => {
    if (!version || busy) return;
    setBusy(true); setError('');
    try {
      const result = await api.tasks.getPublication(taskId, version, template);
      const binary = atob(result.archive_base64);
      const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
      const link = document.createElement('a'); link.href = url; link.download = result.filename;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Publication export failed');
    } finally { setBusy(false); }
  };
  return <div className="print:hidden flex flex-wrap items-center gap-2 text-xs my-3">
    {version && showRevisionLink && <Link href={`/research/${taskId}/revisions?version=${version}`} className="rounded border px-3 py-2 font-medium">
      {isEn ? 'Revise & view versions' : 'Sửa bài & xem phiên bản'}
    </Link>}
    <label className="font-medium" htmlFor="publication-template">{isEn ? 'Publication source' : 'Mẫu xuất bản'}</label>
    <select id="publication-template" value={template} onChange={e => setTemplate(e.target.value as typeof template)} disabled={busy} className="border rounded px-2 py-2 bg-white text-zinc-900">
      <option value="IEEE_CONFERENCE">IEEE Conference</option><option value="ACM_SIGCONF">ACM SIGCONF</option>
    </select>
    <button disabled={busy || !version} onClick={() => void download()} className="rounded border px-3 py-2 font-medium disabled:opacity-50">
      {busy ? (isEn ? 'Preparing…' : 'Đang tạo…') : (isEn ? 'Download LaTeX + figures' : 'Tải LaTeX + hình vẽ')}
    </button>
    <span className="text-zinc-500">{isEn ? 'Compile the ZIP with XeLaTeX / Overleaf.' : 'Biên dịch ZIP bằng XeLaTeX / Overleaf.'}</span>
    <ExperimentBundleExport taskId={taskId} version={version} isEn={isEn} />
    {error && <p role="alert" className="w-full text-red-700">{error}</p>}
  </div>;
}

export function PublicationArticle({ metadata, ...props }: ViewerProps & { metadata?: Record<string, unknown> }) {
  const raw = metadata?.scientific_figures;
  const figures = new Map((Array.isArray(raw) ? raw : []).filter((value): value is { id: string; caption: string; alt: string; svg: string; number: number } =>
    value && typeof value.id === 'string' && typeof value.svg === 'string' && typeof value.caption === 'string'
    && value.svg.length < 200000 && !/<script|foreignObject|\bhref\s*=/i.test(value.svg)
  ).map(value => [value.id, value]));
  const pieces = props.content.split(/(!\[[^\]]*\]\(figures\/[a-z_-]+\.svg\))/g);
  return <article className="font-serif leading-7">{pieces.map((piece, index) => {
    const match = piece.match(/^!\[[^\]]*\]\(figures\/([a-z_-]+)\.svg\)$/);
    const figure = match && figures.get(match[1]);
    if (!figure) return <MarkdownViewer key={index} {...props} content={piece} />;
    return <figure key={index} id={`figure-${figure.id}`} className="my-7 break-inside-avoid">
      {/* SVG is generated from bounded server metrics, displayed as an inert image. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(figure.svg)}`} alt={figure.alt || figure.caption} className="w-full h-auto max-h-96 object-contain" />
      <figcaption className="mt-2 text-center text-sm font-serif">Figure {figure.number}. {figure.caption}</figcaption>
    </figure>;
  })}</article>;
}
