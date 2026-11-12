'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';

export default function LoginPage() {
  const router = useRouter();
  const { language, setLanguage } = useLanguage();
  const isEn = language === 'en';

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [nextPath, setNextPath] = useState('/dashboard');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [accountDeleted, setAccountDeleted] = useState(false);

  useEffect(() => {
    setAccountDeleted(new URLSearchParams(window.location.search).get('account') === 'deleted');
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
      setError(
        err instanceof Error
          ? err.message
          : isEn ? 'Unable to authenticate. Please check your credentials.' : 'Không thể đăng nhập. Vui lòng thử lại.'
      );
    } finally {
      setWorking(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50 px-4 py-12 text-zinc-900 flex items-center justify-center">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm">
        {accountDeleted && <p role="status" className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{isEn ? 'Your account is closed. Research and file cleanup is in progress.' : 'Tài khoản đã đóng. Hệ thống đang dọn các bài nghiên cứu và file.'}</p>}
        <div className="flex items-center justify-between">
          <Link href="/" className="text-sm font-semibold text-zinc-900 flex items-center gap-2">
            <span className="w-6 h-6 rounded-md bg-zinc-900 text-white flex items-center justify-center text-xs font-semibold">S</span>
            <span>Synthia</span>
          </Link>
          <div className="flex items-center border border-zinc-200 rounded-md p-0.5 bg-zinc-50 text-[11px] font-medium">
            <button
              type="button"
              onClick={() => setLanguage('en')}
              className={`px-1.5 py-0.5 rounded transition-colors ${
                isEn ? 'bg-white text-zinc-900 font-semibold shadow-2xs' : 'text-zinc-500 hover:text-zinc-800'
              }`}
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage('vi')}
              className={`px-1.5 py-0.5 rounded transition-colors ${
                !isEn ? 'bg-white text-zinc-900 font-semibold shadow-2xs' : 'text-zinc-500 hover:text-zinc-800'
              }`}
            >
              VI
            </button>
          </div>
        </div>

        <h1 className="mt-6 text-2xl font-semibold">
          {mode === 'login'
            ? (isEn ? 'Sign in to Synthia' : 'Đăng nhập')
            : (isEn ? 'Create an Account' : 'Tạo tài khoản')}
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          {isEn
            ? 'Access your research workspaces, track agent runs, and view reports.'
            : 'Lưu và tiếp tục các bài nghiên cứu trong không gian của bạn.'}
        </p>

        <form onSubmit={submit} className="mt-7 space-y-4">
          {mode === 'register' && (
            <>
              <label className="block text-sm font-medium">
                {isEn ? 'Username' : 'Tên đăng nhập'}
                <input
                  className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900 text-sm"
                  value={username}
                  onChange={event => setUsername(event.target.value)}
                  required
                  minLength={3}
                  maxLength={50}
                  autoComplete="username"
                />
              </label>
              <label className="block text-sm font-medium">
                {isEn ? 'Full name (optional)' : 'Họ và tên (không bắt buộc)'}
                <input
                  className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900 text-sm"
                  value={fullName}
                  onChange={event => setFullName(event.target.value)}
                  maxLength={100}
                  autoComplete="name"
                />
              </label>
            </>
          )}

          <label className="block text-sm font-medium">
            Email
            <input
              className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900 text-sm"
              type="email"
              value={email}
              onChange={event => setEmail(event.target.value)}
              required
              autoComplete="email"
            />
          </label>

          <label className="block text-sm font-medium">
            {isEn ? 'Password' : 'Mật khẩu'}
            <input
              className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900 text-sm"
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              required
              minLength={mode === 'register' ? 8 : undefined}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </label>

          {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          <button
            className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 font-medium text-white disabled:opacity-50 text-sm transition-colors hover:bg-zinc-800"
            type="submit"
            disabled={working}
          >
            {working
              ? (isEn ? 'Processing...' : 'Đang xử lý...')
              : mode === 'login'
              ? (isEn ? 'Sign in' : 'Đăng nhập')
              : (isEn ? 'Create account & sign in' : 'Tạo tài khoản và đăng nhập')}
          </button>
        </form>

        <button
          className="mt-5 text-sm text-zinc-600 hover:text-zinc-900 underline block cursor-pointer transition-colors"
          type="button"
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
        >
          {mode === 'login'
            ? (isEn ? "Don't have an account? Sign up" : 'Chưa có tài khoản? Đăng ký')
            : (isEn ? 'Already have an account? Sign in' : 'Đã có tài khoản? Đăng nhập')}
        </button>
      </div>
    </main>
  );
}
