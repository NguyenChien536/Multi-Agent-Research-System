'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';
import {
  ArrowRight,
  Mail,
  Lock,
  User,
} from 'lucide-react';

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
    <main className="min-h-screen bg-[#FAF9F7] text-stone-900 flex flex-col justify-between selection:bg-stone-900 selection:text-white">
      {/* Top Header */}
      <header className="w-full max-w-6xl mx-auto px-6 sm:px-8 py-5 flex items-center justify-between z-20">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="w-8 h-8 rounded-xl bg-stone-900 text-white flex items-center justify-center text-sm font-bold shadow-2xs group-hover:bg-stone-800 transition-colors">
            S
          </span>
          <span className="text-xl font-bold tracking-tight text-stone-950 font-serif">Synthia</span>
          <span className="hidden sm:inline-block text-[11px] font-medium text-stone-500 tracking-wider pl-2.5 border-l border-stone-300">
            {isEn ? 'Academic Research' : 'Nghiên cứu học thuật'}
          </span>
        </Link>

        {/* Language switch */}
        <div className="flex items-center border border-stone-200/90 rounded-full p-1 bg-white shadow-2xs text-xs font-semibold">
          <button
            type="button"
            onClick={() => setLanguage('en')}
            className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
              isEn ? 'bg-stone-900 text-white shadow-2xs font-bold' : 'text-stone-600 hover:text-stone-900 font-semibold'
            }`}
          >
            EN
          </button>
          <button
            type="button"
            onClick={() => setLanguage('vi')}
            className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
              !isEn ? 'bg-stone-900 text-white shadow-2xs font-bold' : 'text-stone-600 hover:text-stone-900 font-semibold'
            }`}
          >
            VI
          </button>
        </div>
      </header>

      {/* Main Content: Centered, Distraction-Free Auth Card */}
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 py-8 z-10">
        <div className="w-full max-w-md bg-white rounded-3xl border border-stone-200/90 p-8 sm:p-10 shadow-[0_12px_40px_rgba(0,0,0,0.04)]">
          {accountDeleted && (
            <div role="status" className="mb-5 rounded-xl bg-emerald-50 border border-emerald-200/80 p-3.5 text-xs text-emerald-900 font-medium leading-relaxed">
              {isEn
                ? 'Your account has been closed. Data cleanup is completed.'
                : 'Tài khoản của bạn đã được đóng. Dữ liệu bài nghiên cứu đã được xử lý hoàn tất.'}
            </div>
          )}

          {/* Segmented Mode Toggle (Sign In vs Register) */}
          <div className="grid grid-cols-2 p-1 bg-stone-100/90 rounded-2xl border border-stone-200/70 mb-7">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); }}
              className={`py-2 px-3 rounded-xl text-xs font-bold transition-all cursor-pointer text-center ${
                mode === 'login'
                  ? 'bg-white text-stone-950 shadow-2xs'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              {isEn ? 'Sign In' : 'Đăng nhập'}
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(''); }}
              className={`py-2 px-3 rounded-xl text-xs font-bold transition-all cursor-pointer text-center ${
                mode === 'register'
                  ? 'bg-white text-stone-950 shadow-2xs'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              {isEn ? 'Create Account' : 'Tạo tài khoản'}
            </button>
          </div>

          {/* Title & Subtitle */}
          <div className="space-y-1.5 mb-6 text-left">
            <h1 className="text-2xl sm:text-3xl font-bold font-serif text-stone-950 tracking-tight">
              {mode === 'login'
                ? (isEn ? 'Welcome back' : 'Chào mừng trở lại')
                : (isEn ? 'Create an account' : 'Tạo tài khoản mới')}
            </h1>
            <p className="text-xs sm:text-sm text-stone-600 leading-relaxed font-normal">
              {mode === 'login'
                ? (isEn
                  ? 'Enter your credentials to continue your research.'
                  : 'Đăng nhập để tiếp tục các dự án nghiên cứu của bạn.')
                : (isEn
                  ? 'Join Synthia to conduct evidence-grounded research.'
                  : 'Bắt đầu không gian nghiên cứu khoa học chuẩn mực.')}
            </p>
          </div>

          {/* Auth Form */}
          <form onSubmit={submit} className="space-y-4 text-left">
            {mode === 'register' && (
              <>
                <label className="block text-xs font-bold text-stone-800">
                  {isEn ? 'Username' : 'Tên đăng nhập'}
                  <div className="mt-1.5 relative">
                    <User className="absolute left-3.5 top-3 text-stone-400" size={16} />
                    <input
                      className="w-full rounded-xl border border-stone-300 bg-white pl-10 pr-3.5 py-2.5 text-sm text-stone-900 outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 transition-colors"
                      value={username}
                      onChange={event => setUsername(event.target.value)}
                      placeholder={isEn ? 'e.g. researcher42' : 'VD: nguyenvana'}
                      required
                      minLength={3}
                      maxLength={50}
                      autoComplete="username"
                    />
                  </div>
                </label>

                <label className="block text-xs font-bold text-stone-800">
                  {isEn ? 'Full name (optional)' : 'Họ và tên (không bắt buộc)'}
                  <div className="mt-1.5 relative">
                    <User className="absolute left-3.5 top-3 text-stone-400" size={16} />
                    <input
                      className="w-full rounded-xl border border-stone-300 bg-white pl-10 pr-3.5 py-2.5 text-sm text-stone-900 outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 transition-colors"
                      value={fullName}
                      onChange={event => setFullName(event.target.value)}
                      placeholder={isEn ? 'e.g. Dr. Alex Mercer' : 'VD: Nguyễn Văn A'}
                      maxLength={100}
                      autoComplete="name"
                    />
                  </div>
                </label>
              </>
            )}

            <label className="block text-xs font-bold text-stone-800">
              Email
              <div className="mt-1.5 relative">
                <Mail className="absolute left-3.5 top-3 text-stone-400" size={16} />
                <input
                  className="w-full rounded-xl border border-stone-300 bg-white pl-10 pr-3.5 py-2.5 text-sm text-stone-900 outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 transition-colors"
                  type="email"
                  value={email}
                  onChange={event => setEmail(event.target.value)}
                  placeholder={isEn ? 'scholar@university.edu' : 'tenban@truong.edu.vn'}
                  required
                  autoComplete="email"
                />
              </div>
            </label>

            <label className="block text-xs font-bold text-stone-800">
              {isEn ? 'Password' : 'Mật khẩu'}
              <div className="mt-1.5 relative">
                <Lock className="absolute left-3.5 top-3 text-stone-400" size={16} />
                <input
                  className="w-full rounded-xl border border-stone-300 bg-white pl-10 pr-3.5 py-2.5 text-sm text-stone-900 outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 transition-colors"
                  type="password"
                  value={password}
                  onChange={event => setPassword(event.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={mode === 'register' ? 8 : undefined}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                />
              </div>
            </label>

            {error && (
              <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50/90 p-3 text-xs text-rose-800 font-medium leading-relaxed">
                {error}
              </p>
            )}

            <button
              className="w-full rounded-xl bg-stone-900 hover:bg-stone-800 text-white font-bold py-3 px-4 text-xs sm:text-sm tracking-wide transition-all shadow-xs disabled:opacity-40 flex items-center justify-center gap-2 cursor-pointer mt-2"
              type="submit"
              disabled={working}
            >
              {working ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>
                    {mode === 'login'
                      ? (isEn ? 'Sign In' : 'Đăng nhập')
                      : (isEn ? 'Create Account' : 'Tạo tài khoản')}
                  </span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Bottom Quick Switch Link */}
          <div className="mt-6 pt-5 border-t border-stone-100 text-center">
            <button
              type="button"
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
              className="text-xs font-medium text-stone-600 hover:text-stone-950 transition-colors cursor-pointer"
            >
              {mode === 'login'
                ? (isEn ? "Don't have an account? Sign up" : 'Chưa có tài khoản? Đăng ký ngay')
                : (isEn ? 'Already have an account? Sign in' : 'Đã có tài khoản? Đăng nhập ngay')}
            </button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full px-6 py-4 text-center text-xs text-stone-400 font-normal border-t border-stone-200/60 z-10">
        © 2026 Synthia. All rights reserved.
      </footer>
    </main>
  );
}
