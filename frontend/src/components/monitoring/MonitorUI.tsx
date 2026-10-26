import { Activity, AlertTriangle, RefreshCw } from 'lucide-react';
import { statusLabel } from '@/lib/monitoring';

export function StatusPill({ status }: { status: string }) {
  const tone = status === 'RUNNING' || status === 'QUEUED' ? 'bg-blue-50 text-blue-700 border-blue-100'
    : status === 'COMPLETED' || status === 'SUCCESS' ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
    : status === 'FAILED' ? 'bg-red-50 text-red-700 border-red-100'
    : status.startsWith('WAITING') || status === 'NEEDS_REVIEW' ? 'bg-amber-50 text-amber-800 border-amber-100'
    : 'bg-zinc-100 text-zinc-600 border-zinc-200';
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${tone}`}>
    <span className={`h-1.5 w-1.5 rounded-full bg-current ${status === 'RUNNING' ? 'animate-pulse' : ''}`} />
    {statusLabel(status)}
  </span>;
}

export function PollStatus({ error, lastSuccess, refresh }: {
  error: string; lastSuccess: Date | null; refresh: () => void;
}) {
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-500">
      <span className="flex items-center gap-2"><Activity size={14} />
        {lastSuccess ? `Đồng bộ lúc ${lastSuccess.toLocaleTimeString('vi-VN')}` : error ? 'Chưa có dữ liệu đồng bộ' : 'Đang kết nối máy chủ…'}
      </span>
      <button onClick={refresh} className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-zinc-700 hover:bg-zinc-50">
        <RefreshCw size={13} /> Cập nhật
      </button>
    </div>
    {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <AlertTriangle size={18} className="shrink-0 mt-0.5" />
      <div><p className="font-medium">Chưa đồng bộ được trạng thái mới</p>
        <p className="mt-1">{error}</p>
        {lastSuccess && <p className="mt-1">Dữ liệu bên dưới là lần nhận thành công gần nhất. Hệ thống sẽ thử kết nối lại.</p>}
      </div>
    </div>}
  </div>;
}

export function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'medium' }) : 'Chưa ghi nhận';
}
