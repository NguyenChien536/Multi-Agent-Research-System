'use client';
import { useEffect, useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import type { ModelConnectionInput } from '@/types';
import { ModelConnectionFields } from './ModelConnectionFields';

const empty: ModelConnectionInput = {api_key: '', base_url: '', model: '', input_price_per_million: 0, output_price_per_million: 0};

export function ModelSettingsPanel({isEn, taskId}: {isEn: boolean; taskId?: string}) {
  const [serverMode, setServerMode] = useState(false);
  const [scope, setScope] = useState<'default' | 'task'>(taskId ? 'task' : 'default');
  const [value, setValue] = useState<ModelConnectionInput | null>({...empty});
  const [savedRoot, setSavedRoot] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [locked, setLocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);
  const signedIn = api.auth.hasSession();
  useEffect(() => {
    if (!signedIn) { setLoading(false); return; }
    let active = true;
    setLoading(true); setError(''); setNotice('');
    const load = async () => {
      const options = await api.tasks.modelConnectionOptions();
      if (active) setServerMode(!!options.use_server_providers);
      let profile: Omit<ModelConnectionInput,'api_key'> | null | undefined;
      let key = false;
      let lock = false;
      if (scope === 'task' && taskId) {
        const task = await api.tasks.get(taskId);
        profile = task.model_connection;
        key = !!profile && !task.model_connection?.revoked;
        lock = ['RUNNING','QUEUED'].includes(task.status);
      } else {
        const result = await api.settings.getModelConnection();
        profile = result.connection;
        key = !!result.connection?.has_key;
      }
      if (active) {
        setValue(profile ? {api_key:'', base_url:profile.base_url, model:profile.model,
          input_price_per_million:profile.input_price_per_million, output_price_per_million:profile.output_price_per_million,
          output_token_limit: profile.output_token_limit || 8192, reasoning_effort: profile.reasoning_effort || 'low'} : {...empty});
        setSavedRoot(profile?.base_url || ''); setHasKey(key); setLocked(lock);
      }
    };
    load().catch(() => { if (active) setError(isEn ? 'Could not load model settings.' : 'Không tải được cấu hình model.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [scope, taskId, signedIn, refresh, isEn]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!value) return;
    setBusy(true); setError(''); setNotice('');
    const payload = {...value, api_key: value.api_key || undefined};
    try {
      if (scope === 'task' && taskId) await api.settings.updateTaskConnection(taskId, payload);
      else await api.settings.saveModelConnection(payload);
      setHasKey(true); setSavedRoot(value.base_url); setValue({...value, api_key:''});
      setNotice(scope === 'task'
        ? (isEn ? 'Saved for this article.' : 'Đã lưu cho bài hiện tại.')
        : (isEn ? 'Saved as default for new articles.' : 'Đã lưu mặc định cho bài mới.'));
      window.dispatchEvent(new Event('synthia-model-settings'));
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save settings'); }
    finally { setBusy(false); }
  }

  async function applyDefault() {
    if (!taskId) return;
    setBusy(true); setError('');
    try { await api.settings.applyDefault(taskId); setRefresh(v=>v+1); window.dispatchEvent(new Event('synthia-model-settings')); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to apply settings'); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm(isEn ? 'Remove your default API connection? Existing articles keep their own connection.' : 'Xóa kết nối mặc định? Các bài đã tạo vẫn giữ kết nối riêng.')) return;
    setBusy(true);
    try { await api.settings.removeModelConnection(); setValue({...empty}); setHasKey(false); setSavedRoot(''); window.dispatchEvent(new Event('synthia-model-settings')); }
    catch { setError(isEn ? 'Could not remove connection.' : 'Chưa xóa được kết nối.'); }
    finally { setBusy(false); }
  }
  async function saveAsDefault() {
    if (!taskId) return;
    setBusy(true); setError('');
    try {
      await api.settings.saveTaskAsDefault(taskId);
      setNotice(isEn?'Saved as default for new articles.':'Đã đặt làm mặc định cho bài mới.');
      window.dispatchEvent(new Event('synthia-model-settings'));
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save default'); }
    finally { setBusy(false); }
  }
  if (!signedIn) return <p className="text-sm">{isEn ? 'Sign in to save your API connection.' : 'Đăng nhập để lưu kết nối API.'}</p>;
  return <section className="space-y-3">
    <h4 className="font-semibold">{isEn ? 'API & model' : 'API & model'}</h4>
    {serverMode && <p className="text-sm text-zinc-600">{isEn ? 'Your saved connection takes priority. Articles without a personal connection use the server provider.' : 'Kết nối riêng được ưu tiên. Bài không có kết nối riêng dùng provider máy chủ.'}</p>}
    <div className="flex gap-2 text-sm">
      <button type="button" aria-pressed={scope==='default'} onClick={()=>setScope('default')} className={`rounded-lg px-3 py-2 ${scope==='default'?'bg-zinc-900 text-white':'bg-zinc-100'}`}>{isEn?'Default for new articles':'Mặc định cho bài mới'}</button>
      {taskId && <button type="button" aria-pressed={scope==='task'} onClick={()=>setScope('task')} className={`rounded-lg px-3 py-2 ${scope==='task'?'bg-zinc-900 text-white':'bg-zinc-100'}`}>{isEn?'Current article':'Bài hiện tại'}</button>}
    </div>
    {loading ? <p>{isEn?'Loading…':'Đang tải…'}</p> : <form onSubmit={save} className="space-y-3">
      {locked && <p role="status" className="text-amber-700">{isEn?'Stop the article before changing its connection.':'Dừng bài trước khi đổi kết nối.'}</p>}
      <fieldset disabled={locked || busy}>
        <ModelConnectionFields value={value} onChange={setValue} isEn={isEn} hideToggle
          keyRequired={!hasKey || value?.base_url !== savedRoot} taskId={scope === 'task' ? taskId : undefined} />
      </fieldset>
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={busy || locked || !value} className="rounded-lg bg-zinc-900 px-4 py-2 text-white disabled:opacity-40">{busy?(isEn?'Saving…':'Đang lưu…'):scope==='task'?(isEn?'Save for this article':'Lưu cho bài này'):(isEn?'Save default':'Lưu mặc định')}</button>
        {scope==='task' && <button type="button" disabled={busy || locked} onClick={applyDefault} className="rounded-lg border px-3 py-2 disabled:opacity-40">{isEn?'Use saved default':'Dùng cấu hình mặc định'}</button>}
        {scope==='task' && hasKey && <button type="button" disabled={busy} onClick={saveAsDefault} className="rounded-lg border px-3 py-2">{isEn?'Save as default':'Đặt làm mặc định'}</button>}
        {scope==='default' && hasKey && <button type="button" disabled={busy} onClick={remove} className="rounded-lg border px-3 py-2">{isEn?'Remove':'Xóa kết nối'}</button>}
      </div>
    </form>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
  </section>;
}
