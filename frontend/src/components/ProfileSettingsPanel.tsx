'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { api, APIError } from '@/lib/api';
import type { UserProfileUpdate, UserResponse } from '@/types';

export function ProfileSettingsPanel({ isEn }: { isEn: boolean }) {
  const id = useId();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);
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
      setEditing(false);
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
    if (!profile || !editing || !changed || saving || deleting) return;
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

  function cancelEdit() {
    if (!profile) return;
    setFullName(profile.full_name || '');
    setUsername(profile.username);
    setEmail(profile.email);
    setPassword('');
    setError('');
    setNotice('');
    setEditing(false);
  }

  function closeDeletion() {
    setDeleteOpen(false);
    setDeletePassword('');
    setConfirmation('');
    setError('');
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!deleteOpen || confirmation !== 'DELETE' || !deletePassword || deleting) return;
    setDeleting(true);
    setError('');
    setNotice('');
    try {
      await api.auth.deleteAccount({ current_password: deletePassword, confirmation });
      api.auth.logout();
      router.replace('/login?account=deleted');
    } catch (err) {
      const status = err instanceof APIError ? err.status : 0;
      setError(status === 403
        ? (isEn ? 'Your current password is incorrect.' : 'Mật khẩu hiện tại không đúng.')
        : (isEn ? 'Unable to delete your account. Try again.' : 'Chưa xóa được tài khoản. Vui lòng thử lại.'));
      setDeleting(false);
    } finally {
      setDeletePassword('');
    }
  }

  if (loading) return <p role="status" className="text-sm text-zinc-500">{isEn ? 'Loading profile…' : 'Đang tải thông tin…'}</p>;
  if (!profile) return <div className="space-y-2">
    <p role="alert" className="text-sm text-red-700">{error}</p>
    <button type="button" onClick={() => setRefresh(value => value + 1)} className="text-sm underline">{isEn ? 'Try again' : 'Thử lại'}</button>
  </div>;

  const inputClass = 'mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 disabled:bg-zinc-100';
  return <section aria-labelledby={`${id}-title`} className="space-y-4">
    <div className="flex items-center justify-between gap-3">
      <h2 id={`${id}-title`} className="font-semibold text-zinc-900">{isEn ? 'Personal information' : 'Thông tin cá nhân'}</h2>
      {!editing && !deleteOpen && <button type="button" onClick={() => { setEditing(true); setNotice(''); setError(''); }} className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-50">
        {isEn ? 'Edit' : 'Chỉnh sửa'}
      </button>}
    </div>
    {!editing && <dl className="space-y-3 text-sm">
      <div><dt className="text-zinc-500">{isEn ? 'Full name' : 'Họ và tên'}</dt><dd className="mt-0.5 break-words font-medium">{profile.full_name || (isEn ? 'Not provided' : 'Chưa cập nhật')}</dd></div>
      <div><dt className="text-zinc-500">{isEn ? 'Username' : 'Tên đăng nhập'}</dt><dd className="mt-0.5 break-words font-medium">{profile.username}</dd></div>
      <div><dt className="text-zinc-500">Email</dt><dd className="mt-0.5 break-words font-medium">{profile.email}</dd></div>
    </dl>}
    {editing && <form onSubmit={save} className="space-y-4">
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
      <div className="flex gap-2">
      <button type="submit" disabled={saving || !changed} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
        {saving ? (isEn ? 'Saving…' : 'Đang lưu…') : (isEn ? 'Save changes' : 'Lưu thay đổi')}
      </button>
      <button type="button" disabled={saving} onClick={cancelEdit} className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium disabled:opacity-40">{isEn ? 'Cancel' : 'Hủy'}</button>
      </div>
    </form>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
    {!editing && <div className="border-t border-zinc-200 pt-4">
      {!deleteOpen ? <button type="button" onClick={() => { setDeleteOpen(true); setError(''); setNotice(''); }} className="text-sm font-medium text-red-700 hover:underline">
        {isEn ? 'Delete account' : 'Xóa tài khoản'}
      </button> : <form onSubmit={deleteAccount} className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-4" aria-labelledby={`${id}-delete-title`}>
        <h3 id={`${id}-delete-title`} className="font-semibold text-red-900">{isEn ? 'Delete this account?' : 'Xóa tài khoản này?'}</h3>
        <p className="text-sm text-red-900">{isEn ? 'You will be signed out immediately. Your research and files will be deleted in the background. This request cannot be undone.' : 'Bạn sẽ đăng xuất ngay. Các bài nghiên cứu và file của tài khoản được xóa ở nền. Không thể hủy yêu cầu này.'}</p>
        <fieldset disabled={deleting} className="space-y-3">
          <div>
            <label htmlFor={`${id}-delete-password`} className="text-sm font-medium">{isEn ? 'Current password' : 'Mật khẩu hiện tại'}</label>
            <input id={`${id}-delete-password`} name="delete_password" type="password" required maxLength={128} autoComplete="current-password" value={deletePassword} onChange={event => setDeletePassword(event.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor={`${id}-delete-confirmation`} className="text-sm font-medium">{isEn ? 'Type DELETE to confirm' : 'Nhập DELETE để xác nhận'}</label>
            <input id={`${id}-delete-confirmation`} name="confirmation" required pattern="DELETE" autoComplete="off" spellCheck={false} value={confirmation} onChange={event => setConfirmation(event.target.value)} className={inputClass} />
          </div>
        </fieldset>
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={deleting || confirmation !== 'DELETE' || !deletePassword} className="rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{deleting ? (isEn ? 'Deleting…' : 'Đang xóa…') : (isEn ? 'Permanently delete account' : 'Xóa vĩnh viễn tài khoản')}</button>
          <button type="button" disabled={deleting} onClick={closeDeletion} className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm disabled:opacity-40">{isEn ? 'Cancel' : 'Hủy'}</button>
        </div>
      </form>}
    </div>}
  </section>;
}
