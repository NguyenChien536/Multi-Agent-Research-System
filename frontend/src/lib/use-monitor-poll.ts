'use client';

import { useCallback, useEffect, useState } from 'react';

/** Wait for each request before scheduling the next; abort on navigation/retry. */
export function useMonitorPoll<T>(load: (signal: AbortSignal) => Promise<T>, interval = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [lastSuccess, setLastSuccess] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision(value => value + 1), []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    let retry = true;
    // A different load function means another paper/page: never show the old one.
    setData(null);
    setLastSuccess(null);
    setLoading(true);
    setError('');
    async function poll() {
      if (!active) return;
      if (document.visibilityState === 'hidden') {
        timer = setTimeout(poll, interval);
        return;
      }
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 15000);
      try {
        const value = await load(controller.signal);
        if (active) {
          setData(value);
          setLastSuccess(new Date());
          setError('');
        }
      } catch (reason) {
        if (active) {
          const status = reason && typeof reason === 'object' && 'status' in reason ? reason.status : null;
          setError(Number(status) === 404 ? 'Bài nghiên cứu không tồn tại hoặc bạn không có quyền xem.'
            : Number(status) === 401 ? 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
            : Number(status) === 403 ? 'Bạn không có quyền xem bài nghiên cứu này.'
            : 'Không thể tải tiến độ mới. Kiểm tra kết nối và thử lại.');
          if ([401, 403, 404, 422].includes(Number(status))) {
            setData(null);
            setLastSuccess(null);
            retry = false;
          }
        }
      } finally {
        clearTimeout(timeout);
        if (active) {
          setLoading(false);
          if (retry) timer = setTimeout(poll, interval);
        }
      }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); controller?.abort(); };
  }, [load, interval, revision]);
  return { data, error, loading, lastSuccess, refresh };
}
