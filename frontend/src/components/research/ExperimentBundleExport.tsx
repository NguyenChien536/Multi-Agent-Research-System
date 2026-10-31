'use client';

import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';

export function ExperimentBundleExport({ taskId, version, isEn }: { taskId: string; version?: number; isEn: boolean }) {
  const [availability, setAvailability] = useState<{ available: boolean; computational: boolean; reason?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const request = new AbortController();
    setAvailability(null); setError(''); setBusy(false);
    if (version) api.tasks.getExperimentBundleAvailability(taskId, version, request.signal)
      .then(value => { if (!request.signal.aborted) setAvailability(value); })
      .catch(err => { if (!request.signal.aborted) setError(err instanceof Error ? err.message : 'Export unavailable'); });
    return () => { request.abort(); controller.current?.abort(); };
  }, [taskId, version]);
  const download = async () => {
    if (!version || busy || !availability?.available) return;
    const request = new AbortController(); controller.current = request;
    setBusy(true); setError('');
    try {
      const blob = await api.tasks.getExperimentBundle(taskId, version, request.signal);
      if (request.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `experiment-v${version}.zip`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      if (!request.signal.aborted) setError(err instanceof Error ? err.message : 'Experiment export failed');
    } finally { if (!request.signal.aborted) setBusy(false); }
  };
  if (!availability?.computational && !error) return null;
  return <div className="flex flex-wrap items-center gap-2">
    {availability?.computational && <>
      <button type="button" disabled={!availability.available || busy} onClick={() => void download()}
        className="rounded border px-3 py-2 font-medium disabled:opacity-50">
        {busy ? (isEn ? 'Preparing…' : 'Đang tạo…') : (isEn ? 'Download experiment + dataset' : 'Tải thí nghiệm + dữ liệu')}
      </button>
      <span className="text-zinc-500">{availability.available
        ? (isEn ? 'Includes your dataset. Keep the ZIP private.' : 'Có dữ liệu của bạn. Giữ riêng tư gói ZIP.')
        : (isEn ? 'A new experiment is required to capture complete replay snapshots.' : 'Cần chạy thí nghiệm mới để lưu đủ dữ liệu tái lập.')}</span>
    </>}
    {error && <p role="alert" className="w-full text-red-700">{error}</p>}
  </div>;
}
