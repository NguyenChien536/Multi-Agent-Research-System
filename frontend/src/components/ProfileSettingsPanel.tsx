'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import { api, APIError } from '@/lib/api';
import type { UserProfileUpdate, UserResponse } from '@/types';

export function ProfileSettingsPanel({ isEn }: { isEn: boolean }) {
  const id = useId();
  const [profile, setProfile] = useState<UserResponse | null>(null);
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    const accept = (user: UserResponse) => {
      setProfile(user);
      setFullName(user.full_name || '');
      setUsername(user.username);
      setEmail(user.email);
      setPassword('');
    };
    api.auth.me().then(user => { if (active) accept(user); }).catch(() => {
      if (active) setError(isEn ? 'Unable to load your profile. Try again.' : 'Không tải được thông tin cá nhân. Vui lòng thử lại.');
    }).finally(() => { if (active) setLoading(false); });
    const updated = (event: Event) => accept((event as CustomEvent<UserResponse>).detail);
    window.addEventListener('synthia-profile-updated', updated);
    return () => {
      active = false;
      window.removeEventListener('synthia-profile-updated', updated);
    };
  }, [isEn, refresh]);

  const emailChanged = !!profile && email.trim() !== profile.email;
  const changed = !!profile && (
    (fullName.trim() || null) !== (profile.full_name || null)
    || username.trim() !== profile.username || emailChanged
  );

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile || !changed || saving) return;
    setSaving(true);
    setError('');
    setNotice('');
    const changes: UserProfileUpdate = {};
    if ((fullName.trim() || null) !== (profile.full_name || null)) changes.full_name = fullName.trim() || null;
    if (username.trim() !== profile.username) changes.username = username.trim();
    if (emailChanged) {
      changes.email = email.trim();
      changes.current_password = password;
    }
    try {
      const saved = await api.auth.updateProfile(changes);
      window.dispatchEvent(new CustomEvent<UserResponse>('synthia-profile-updated', { detail: saved }));
      setNotice(isEn ? 'Profile saved.' : 'Đã lưu thông tin cá nhân.');
    } catch (err) {
      const status = err instanceof APIError ? err.status : 0;
      setError(status === 409
        ? (isEn ? 'That username or email is already in use.' : 'Tên đăng nhập hoặc email đã được sử dụng.')
        : status === 403
          ? (isEn ? 'Enter your correct current password to change email.' : 'Nhập đúng mật khẩu hiện tại để đổi email.')
          : status === 422
            ? (isEn ? 'Check your name, username and email format.' : 'Kiểm tra độ dài tên, tên đăng nhập và định dạng email.')
            : (isEn ? 'Unable to save your profile. Try again.' : 'Chưa lưu được thông tin. Vui lòng thử lại.'));
    } finally {
      setPassword('');
      setSaving(false);
    }
  }

  if (loading) return <p role="status" className="text-sm text-zinc-500">{isEn ? 'Loading profile…' : 'Đang tải thông tin…'}</p>;
  if (!profile) return <div className="space-y-2">
    <p role="alert" className="text-sm text-red-700">{error}</p>
    <button type="button" onClick={() => setRefresh(value => value + 1)} className="text-sm underline">{isEn ? 'Try again' : 'Thử lại'}</button>
  </div>;

  const inputClass = 'mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 disabled:bg-zinc-100';
  return <section aria-labelledby={`${id}-title`} className="space-y-4">
    <h2 id={`${id}-title`} className="font-semibold text-zinc-900">{isEn ? 'Personal information' : 'Thông tin cá nhân'}</h2>
    <form onSubmit={save} className="space-y-4">
      <fieldset disabled={saving} className="space-y-3">
        <div>
          <label htmlFor={`${id}-name`} className="text-sm font-medium">{isEn ? 'Full name' : 'Họ và tên'}</label>
          <input id={`${id}-name`} name="full_name" value={fullName} onChange={event => { setFullName(event.target.value); setNotice(''); }} maxLength={100} autoComplete="name" className={inputClass} />
        </div>
        <div>
          <label htmlFor={`${id}-username`} className="text-sm font-medium">{isEn ? 'Username' : 'Tên đăng nhập'}</label>
          <input id={`${id}-username`} name="username" value={username} onChange={event => { setUsername(event.target.value); setNotice(''); }} required minLength={3} maxLength={50} autoComplete="username" className={inputClass} />
        </div>
        <div>
          <label htmlFor={`${id}-email`} className="text-sm font-medium">Email</label>
          <input id={`${id}-email`} name="email" type="email" value={email} onChange={event => { setEmail(event.target.value); setNotice(''); }} required maxLength={255} autoComplete="email" className={inputClass} />
        </div>
        {emailChanged && <div>
          <label htmlFor={`${id}-password`} className="text-sm font-medium">{isEn ? 'Current password' : 'Mật khẩu hiện tại'}</label>
          <input id={`${id}-password`} name="current_password" type="password" value={password} onChange={event => setPassword(event.target.value)} required maxLength={128} autoComplete="current-password" aria-describedby={`${id}-email-hint`} className={inputClass} />
          <p id={`${id}-email-hint`} className="mt-1 text-xs text-zinc-500">{isEn ? 'Use your new email for your next sign-in.' : 'Lần đăng nhập sau hãy dùng email mới.'}</p>
        </div>}
      </fieldset>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
      <button type="submit" disabled={saving || !changed} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
        {saving ? (isEn ? 'Saving…' : 'Đang lưu…') : (isEn ? 'Save changes' : 'Lưu thay đổi')}
      </button>
    </form>
  </section>;
}
