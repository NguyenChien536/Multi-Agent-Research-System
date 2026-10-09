'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [nextPath, setNextPath] = useState('/dashboard');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get('next');
    if (requested?.startsWith('/') && !requested.startsWith('//') && !requested.startsWith('/\\')) {
      setNextPath(requested);
    }
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      if (mode === 'register') {
        await api.auth.register({
          username: username.trim(),
          email: email.trim(),
          password,
          full_name: fullName.trim() || undefined,
        });
      }
      await api.auth.login(email.trim(), password);
      router.replace(nextPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể đăng nhập. Vui lòng thử lại.');
    } finally {
      setWorking(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50 px-4 py-12 text-zinc-900 flex items-center justify-center">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm">
        <Link href="/" className="text-sm font-semibold text-zinc-600">Synthia</Link>
        <h1 className="mt-6 text-2xl font-semibold">{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</h1>
        <p className="mt-2 text-sm text-zinc-500">Lưu và tiếp tục các bài nghiên cứu trong không gian của bạn.</p>
        <form onSubmit={submit} className="mt-7 space-y-4">
          {mode === 'register' && <>
            <label className="block text-sm font-medium">Tên đăng nhập
              <input className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900" value={username} onChange={event => setUsername(event.target.value)} required minLength={3} maxLength={50} autoComplete="username" />
            </label>
            <label className="block text-sm font-medium">Họ và tên (không bắt buộc)
              <input className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900" value={fullName} onChange={event => setFullName(event.target.value)} maxLength={100} autoComplete="name" />
            </label>
          </>}
          <label className="block text-sm font-medium">Email
            <input className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900" type="email" value={email} onChange={event => setEmail(event.target.value)} required autoComplete="email" />
          </label>
          <label className="block text-sm font-medium">Mật khẩu
            <input className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900" type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={mode === 'register' ? 8 : undefined} autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
          </label>
          {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <button className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 font-medium text-white disabled:opacity-50" type="submit" disabled={working}>
            {working ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản và đăng nhập'}
          </button>
        </form>
        <button className="mt-5 text-sm text-zinc-600 underline" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>
          {mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}
        </button>
      </div>
    </main>
  );
}
