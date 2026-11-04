'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import type { ResearchTaskResponse } from '@/types';

export function ModelConnectionSummary({ task, isEn }: { task: ResearchTaskResponse; isEn: boolean }) {
  const [revoked, setRevoked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const connection = task.model_connection;
  if (!connection) return null;
  const isRevoked = revoked || connection.revoked;
  async function revoke() {
    if (!window.confirm(isEn ? 'Remove this key? Future research and question requests for this article will stop.'
      : 'Thu hồi key? Các bước nghiên cứu và hỏi đáp tiếp theo của bài này sẽ dừng.')) return;
    setBusy(true);
    try { await api.tasks.revokeModelConnection(task.id); setRevoked(true); }
    catch { setError(isEn ? 'Could not remove the key. Try again.' : 'Chưa thu hồi được key. Hãy thử lại.'); }
    finally { setBusy(false); }
  }
  return <div className="space-y-2 rounded-xl border border-zinc-200 p-4 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold">{isEn ? 'Your API connection' : 'Kết nối API riêng'}</h3>
      <button type="button" disabled={busy || isRevoked} onClick={revoke}
        className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs disabled:opacity-50">
        {isRevoked ? (isEn ? 'Key removed' : 'Đã thu hồi key') : (isEn ? 'Remove key' : 'Thu hồi key')}
      </button>
    </div>
    <p className="break-all font-mono text-xs">{connection.model} · {connection.base_url}</p>
    <p className="text-xs leading-relaxed text-zinc-500">{isEn
      ? 'Costs use the token prices you declared, not a provider invoice. Public scholarly search and lexical retrieval use no server API credits. Removing the key does not recall a request already in progress.'
      : 'Chi phí tính theo đơn giá bạn khai báo, không phải hóa đơn nhà cung cấp. Tìm nguồn học thuật công khai và truy xuất từ khóa không dùng tín dụng API máy chủ. Thu hồi key không hủy được yêu cầu đã gửi trước đó.'}</p>
    {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
  </div>;
}
