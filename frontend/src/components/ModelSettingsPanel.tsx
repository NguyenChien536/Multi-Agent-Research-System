'use client';
import { useEffect, useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import type { ModelConnectionInput, ModelConnectionCheck } from '@/types';
import { connectionStatusMessage } from '@/lib/model-connection-status';
import { ModelConnectionFields } from './ModelConnectionFields';

const empty: ModelConnectionInput = {api_key: '', base_url: '', model: '', input_price_per_million: 0, output_price_per_million: 0, output_token_limit:32768};

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
  const [editing, setEditing] = useState(false);
  const [check, setCheck] = useState<ModelConnectionCheck | null>(null);
  const [freeTier, setFreeTier] = useState(false);
  const [paidProbe, setPaidProbe] = useState(false);
  const signedIn = api.auth.hasSession();
  useEffect(()=>{ setPaidProbe(false); setCheck(null); },[value?.base_url,value?.model,value?.api_key,value?.structured_output_mode,value?.input_price_per_million,value?.output_price_per_million]);
  useEffect(() => {
    if (!signedIn) { setLoading(false); return; }
    let active = true;
    setLoading(true); setError(''); setNotice(''); setCheck(null); setFreeTier(false); setPaidProbe(false);
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
          output_token_limit: profile.output_token_limit || 8192, reasoning_effort: profile.reasoning_effort || 'low',
          structured_output_mode: profile.structured_output_mode || 'json_object'} : {...empty});
        setSavedRoot(profile?.base_url || ''); setHasKey(key); setLocked(lock); setEditing(!key);
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
      setHasKey(true); setSavedRoot(value.base_url); setValue({...value, api_key:''}); setEditing(false);
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
    try { await api.settings.removeModelConnection(); setValue({...empty}); setHasKey(false); setSavedRoot(''); setEditing(true); setCheck(null); window.dispatchEvent(new Event('synthia-model-settings')); }
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
  async function checkConnection(generate: boolean) {
    if (!value) return;
    setBusy(true); setError(''); setCheck(null);
    if (generate) setPaidProbe(false);
    try {
      setCheck(await api.settings.checkConnection({...value, api_key:value.api_key || undefined,
        task_id:scope==='task' ? taskId : undefined, generate, free_tier_confirmed:freeTier, paid_probe_confirmed:paidProbe}));
    } catch (err) { setError(err instanceof Error ? err.message : (isEn ? 'Check failed.' : 'Chưa kiểm tra được kết nối.')); }
    finally { setBusy(false); }
  }
  if (!signedIn) return <p className="text-sm">{isEn ? 'Sign in to save your API connection.' : 'Đăng nhập để lưu kết nối API.'}</p>;
  return <section className="space-y-3">
    <h4 className="text-lg font-semibold">{isEn ? 'AI connection' : 'Kết nối AI'}</h4>
    {serverMode && <p className="text-sm text-zinc-600">{isEn ? 'Your saved connection takes priority. Articles without a personal connection use the server provider.' : 'Kết nối riêng được ưu tiên. Bài không có kết nối riêng dùng provider máy chủ.'}</p>}
    {!taskId && <p className="text-sm text-zinc-500">{isEn?'Default connection for new articles. Existing articles keep their own settings.':'Kết nối mặc định cho bài mới. Các bài đã tạo giữ cấu hình riêng.'}</p>}
    {taskId && <div className="flex gap-2 text-sm">
      <button type="button" disabled={busy} aria-pressed={scope==='default'} onClick={()=>setScope('default')} className={`rounded-lg px-3 py-2 ${scope==='default'?'bg-zinc-900 text-white':'bg-zinc-100'}`}>{isEn?'Default for new articles':'Mặc định cho bài mới'}</button>
      <button type="button" disabled={busy} aria-pressed={scope==='task'} onClick={()=>setScope('task')} className={`rounded-lg px-3 py-2 ${scope==='task'?'bg-zinc-900 text-white':'bg-zinc-100'}`}>{isEn?'Current article':'Bài hiện tại'}</button>
    </div>}
    {loading ? <p>{isEn?'Loading…':'Đang tải…'}</p> : <form onSubmit={save} className="space-y-3">
      {locked && <p role="status" className="text-amber-700">{isEn?'Stop the article before changing its connection.':'Dừng bài trước khi đổi kết nối.'}</p>}
      {!editing && value && <div className="rounded-xl border bg-zinc-50 p-4">
        <p className="break-words font-medium">{value.model}</p>
        <p className="mt-1 text-sm text-zinc-500">{value.base_url.includes('googleapis.com') ? 'Google Gemini' : value.base_url.includes('openrouter.ai') ? 'OpenRouter' : value.base_url.includes('groq.com') ? 'Groq' : new URL(value.base_url).hostname} · {isEn?'Key saved':'Đã lưu key'}</p>
      </div>}
      {editing && <fieldset disabled={locked || busy}>
        <ModelConnectionFields value={value} onChange={next=>{if(next?.base_url!==value?.base_url)setFreeTier(false);setValue(next);setCheck(null);setNotice('');}} isEn={isEn} hideToggle
          keyRequired={!hasKey || value?.base_url !== savedRoot} taskId={scope === 'task' ? taskId : undefined} />
      </fieldset>}
      {!!value && (value.input_price_per_million > 0 || value.output_price_per_million > 0) && <label className="flex items-center gap-2 text-sm text-zinc-600">
        <input type="checkbox" disabled={busy} checked={paidProbe} onChange={event=>setPaidProbe(event.target.checked)} />
        {isEn ? 'Allow one billable connection test (up to 2,048 output tokens)' : 'Cho phép một lượt thử có tính phí (tối đa 2.048 output token)'}
      </label>}
      {value?.base_url && value.input_price_per_million === 0 && value.output_price_per_million === 0 && value.base_url !== 'https://openrouter.ai/api/v1' && <label className="flex items-center gap-2 text-sm text-zinc-600">
        <input type="checkbox" disabled={busy} checked={freeTier} onChange={event=>setFreeTier(event.target.checked)} />
        {isEn?'This project uses a free tier':'Project này dùng gói miễn phí'}
      </label>}
      <div className="flex flex-wrap gap-2 text-sm">
        <button type="button" disabled={busy || !value?.model || (editing && (!hasKey || value.base_url!==savedRoot) && !value.api_key)} onClick={()=>checkConnection(false)} className="rounded-lg border px-3 py-2 disabled:opacity-40">{isEn?'Check key & quota':'Kiểm tra key & hạn mức'}</button>
        <button type="button" disabled={busy || !value?.model || ((value.input_price_per_million > 0 || value.output_price_per_million > 0) ? !paidProbe : (value.base_url !== 'https://openrouter.ai/api/v1' && !freeTier)) || (editing && (!hasKey || value.base_url!==savedRoot) && !value.api_key)} onClick={()=>checkConnection(true)} className="rounded-lg border px-3 py-2 disabled:opacity-40">{busy?(isEn?'Checking…':'Đang kiểm tra…'):(isEn?'Check response':'Thử phản hồi')}</button>
      </div>
      {check && <div role="status" className={`rounded-xl border p-3 text-sm ${check.status==='ok' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : check.status==='catalog_ok' ? 'border-zinc-200 bg-zinc-50 text-zinc-700' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
        <p>{connectionStatusMessage(check.status,isEn)}</p>
        {check.quota && <p className="mt-1">{isEn?'Daily requests':'Lượt gọi trong ngày'}: {check.quota.used}/{check.quota.limit} · {isEn?'Remaining':'Còn lại'}: {check.quota.remaining}</p>}
      </div>}
      <div className="sticky bottom-0 z-10 flex flex-wrap gap-2 border-t border-zinc-200 bg-white/95 py-3 backdrop-blur-sm">
        {editing ? <><button type="submit" disabled={busy || locked || !value} className="rounded-lg bg-zinc-900 px-4 py-2 text-white disabled:opacity-40">{busy?(isEn?'Please wait…':'Đang xử lý…'):scope==='task'?(isEn?'Save for this article':'Lưu cho bài này'):(isEn?'Save default':'Lưu mặc định')}</button>
          {hasKey && <button type="button" disabled={busy} onClick={()=>setRefresh(v=>v+1)} className="rounded-lg border px-3 py-2">{isEn?'Cancel':'Hủy'}</button>}</>
          : <button type="button" disabled={busy || locked} onClick={()=>{setEditing(true);setCheck(null);setNotice('');}} className="rounded-lg bg-zinc-900 px-4 py-2 text-white disabled:opacity-40">{isEn?'Edit connection':'Chỉnh sửa kết nối'}</button>}
        {scope==='task' && <button type="button" disabled={busy || locked} onClick={applyDefault} className="rounded-lg border px-3 py-2 disabled:opacity-40">{isEn?'Use saved default':'Dùng cấu hình mặc định'}</button>}
        {scope==='task' && hasKey && !editing && <button type="button" disabled={busy} onClick={saveAsDefault} className="rounded-lg border px-3 py-2">{isEn?'Save as default':'Đặt làm mặc định'}</button>}
        {scope==='default' && hasKey && <button type="button" disabled={busy} onClick={remove} className="rounded-lg border px-3 py-2">{isEn?'Remove':'Xóa kết nối'}</button>}
      </div>
    </form>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
  </section>;
}
