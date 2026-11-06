'use client';

import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type { ModelConnectionInput } from '@/types';

interface ProviderMeta {
  label: string;
  placeholder: string;
}

const KNOWN_PROVIDERS: Record<string, ProviderMeta> = {
  'https://openrouter.ai/api/v1': {
    label: 'OpenRouter (openrouter.ai)',
    placeholder: 'openrouter/free',
  },
  'https://api.groq.com/openai/v1': {
    label: 'Groq Cloud (api.groq.com)',
    placeholder: 'llama-3.3-70b-versatile',
  },
  'https://generativelanguage.googleapis.com/v1beta/openai': {
    label: 'Google Gemini (OpenAI-compatible)',
    placeholder: 'gemini-2.5-flash',
  },
  'https://api.deepseek.com/v1': {
    label: 'DeepSeek (api.deepseek.com)',
    placeholder: 'deepseek-chat',
  },
  'https://api.mistral.ai/v1': {
    label: 'Mistral AI (api.mistral.ai)',
    placeholder: 'mistral-small-latest',
  },
  'https://api.openai.com/v1': {
    label: 'OpenAI (api.openai.com)',
    placeholder: 'gpt-4o-mini',
  },
  'https://api.together.xyz/v1': {
    label: 'Together AI (api.together.xyz)',
    placeholder: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
  },
  'https://api.cerebras.ai/v1': {
    label: 'Cerebras (api.cerebras.ai)',
    placeholder: 'llama3.1-70b',
  },
};

export function ModelConnectionFields({ value, onChange, isEn, keyRequired = true, hideToggle = false, taskId }: {
  value: ModelConnectionInput | null;
  onChange: (value: ModelConnectionInput | null) => void;
  isEn: boolean;
  keyRequired?: boolean;
  hideToggle?: boolean;
  taskId?: string;
}) {
  const [roots, setRoots] = useState<string[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<string[]>([]);
  const [schemaModels, setSchemaModels] = useState<Record<string, boolean>>({});
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogError, setCatalogError] = useState('');
  const [catalogChecked, setCatalogChecked] = useState(false);
  const [manualModel, setManualModel] = useState(false);
  const [freeOnly, setFreeOnly] = useState(true);
  const catalogRequest = useRef({sequence: 0});
  useEffect(() => {
    const tracker = catalogRequest.current;
    tracker.sequence++;
    setModels([]); setSchemaModels({}); setCatalogChecked(false); setCatalogError(''); setCatalogBusy(false);
    return () => { tracker.sequence++; };
  }, [value?.base_url, value?.api_key, taskId, freeOnly]);
  useEffect(() => {
    let active = true;
    setLoadError(false);
    setLoading(true);
    api.tasks.modelConnectionOptions().then(result => {
      if (active) { setRoots(result.base_urls); setLoadError(result.base_urls.length === 0); }
    }).catch(() => { if (active) setLoadError(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);
  const update = (patch: Partial<ModelConnectionInput>) => { if (value) onChange({ ...value, ...patch }); };
  const inputClass = 'mt-1 w-full rounded-lg border border-zinc-200 bg-white p-2 text-sm outline-none focus:ring-2 focus:ring-zinc-400';

  async function loadModels() {
    if (!value?.base_url) return;
    const request = ++catalogRequest.current.sequence;
    setCatalogBusy(true); setCatalogError(''); setCatalogChecked(false);
    try {
      const result = await api.settings.discoverModels({base_url: value.base_url,
        api_key: value.api_key || undefined, task_id: taskId, free_only: freeOnly});
      if (request !== catalogRequest.current.sequence) return;
      const names = result.models.map(model => model.id);
      setSchemaModels(Object.fromEntries(result.models.map(model => [model.id, !!model.supports_json_schema])));
      setModels(names); setCatalogChecked(true); setManualModel(false);
      // Keep an explicit user choice. Never silently pick a paid model.
      if (!value.model && value.base_url === 'https://openrouter.ai/api/v1' && freeOnly) update({model:'openrouter/free'});
    } catch (err) {
      if (request === catalogRequest.current.sequence) setCatalogError(err instanceof Error ? err.message : (isEn ? 'Unable to load models.' : 'Không tải được model.'));
    } finally { if (request === catalogRequest.current.sequence) setCatalogBusy(false); }
  }

  const handleBaseUrlChange = (newUrl: string) => {
    update({
      structured_output_mode: 'json_object',
      base_url: newUrl,
      api_key: '',
      model: newUrl === 'https://openrouter.ai/api/v1' ? 'openrouter/free' : '',
      input_price_per_million: 0,
      output_price_per_million: 0,
    });
  };

  const activePlaceholder = (value?.base_url && KNOWN_PROVIDERS[value.base_url]?.placeholder)
    || (isEn ? 'Model ID from your provider' : 'Model ID do dịch vụ cung cấp');

  return <section className="space-y-3 border-t border-zinc-100 pt-4">
    {!hideToggle && <label className="flex items-center gap-2 text-sm font-semibold">
      <input type="checkbox" checked={!!value} onChange={event => onChange(event.target.checked ? {
        api_key: '', base_url: '', model: '', input_price_per_million: 0, output_price_per_million: 0,
      } : null)} />
      {isEn ? 'Use my API connection' : 'Dùng API key của tôi'}
    </label>}
    {value && <>
      {loadError && <div role="alert" className="flex items-center justify-between gap-2 text-sm text-red-700">
        <span>{isEn ? 'Could not load API services.' : 'Không tải được danh sách dịch vụ API.'}</span>
        <button type="button" onClick={() => setReload(value => value + 1)} className="underline">{isEn ? 'Retry' : 'Thử lại'}</button>
      </div>}
      <label className="block text-xs font-medium">{isEn ? 'API base URL' : 'Địa chỉ API (base URL)'}
        <select className={inputClass} required disabled={loading} value={value.base_url} onChange={event => handleBaseUrlChange(event.target.value)}>
          <option value="">{loading ? (isEn ? 'Loading services…' : 'Đang tải dịch vụ…') : (isEn ? 'Select API service' : 'Chọn dịch vụ API')}</option>
          {roots.map(root => (
            <option key={root} value={root}>
              {KNOWN_PROVIDERS[root]?.label || root}
            </option>
          ))}
        </select>
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs font-medium">API key
          <input className={inputClass} type="password" required={keyRequired} minLength={8} maxLength={4096} autoComplete="off"
            placeholder={keyRequired ? '' : (isEn ? 'Saved securely · leave blank to keep' : 'Đã lưu an toàn · để trống để giữ key')}
            spellCheck={false} value={value.api_key} onChange={event => update({ api_key: event.target.value })} />
        </label>
        <label className="block text-xs font-medium">{isEn ? 'Model' : 'Model'}
          {!manualModel ? <select className={inputClass} required value={value.model} onChange={event => update({model:event.target.value, structured_output_mode:schemaModels[event.target.value] ? 'json_schema' : 'json_object'})}>
            <option value="">{isEn ? 'Load models, then choose' : 'Tải danh sách rồi chọn model'}</option>
            {value.model && !models.includes(value.model) && <option value={value.model}>{value.model}</option>}
            {models.map(model => <option key={model} value={model}>{model}{schemaModels[model] ? ' · JSON Schema' : ''}</option>)}
          </select> : <input className={inputClass} required maxLength={200} autoComplete="off" spellCheck={false}
            placeholder={activePlaceholder} value={value.model} onChange={event => update({model:event.target.value.trim(), structured_output_mode:'json_object'})} />}
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <button type="button" disabled={catalogBusy || !value.base_url || (keyRequired && !value.api_key)} onClick={loadModels}
          className="rounded-lg border px-3 py-2 font-medium disabled:opacity-40">{catalogBusy ? (isEn ? 'Loading…' : 'Đang tải…') : (isEn ? 'Load available models' : 'Tải danh sách model')}</button>
        <button type="button" className="underline" onClick={()=>setManualModel(v=>!v)}>{manualModel ? (isEn ? 'Choose from list' : 'Chọn từ danh sách') : (isEn ? 'Enter model ID manually' : 'Nhập tên model thủ công')}</button>
        {value.base_url === 'https://openrouter.ai/api/v1' && <label className="flex items-center gap-1"><input type="checkbox" checked={freeOnly} onChange={event=>setFreeOnly(event.target.checked)} />{isEn ? 'Free models only' : 'Chỉ model miễn phí'}</label>}
      </div>
      {catalogError && <p role="alert" className="text-sm text-red-700">{catalogError}</p>}
      {catalogChecked && <p role="status" className="text-xs text-emerald-700">{isEn ? 'Model list loaded. No text was generated. Quota and generation access may differ by model.' : 'Đã tải danh sách; chưa sinh văn bản. Quota và quyền tạo nội dung phụ thuộc model.'}</p>}
      <details className="text-sm text-zinc-700">
        <summary className="cursor-pointer">{isEn ? 'Model options' : 'Tùy chọn model'}</summary>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <label>{isEn ? 'Structured data compatibility' : 'Tương thích dữ liệu có cấu trúc'}
            <select className={inputClass} value={value.structured_output_mode || 'json_object'} onChange={event=>update({structured_output_mode:event.target.value as ModelConnectionInput['structured_output_mode']})}>
              <option value="json_object">{isEn ? 'JSON · broad compatibility' : 'JSON · tương thích rộng'}</option>
              <option value="json_schema">{isEn ? 'JSON Schema · supported endpoints' : 'JSON Schema · endpoint có hỗ trợ'}</option>
            </select>
          </label>
          <label>{isEn?'Output token limit':'Giới hạn token đầu ra'}
            <input type="number" min={1024} max={32768} step={1024} required className={inputClass}
              value={value.output_token_limit || 8192} onChange={event=>update({output_token_limit:Number(event.target.value)})} />
          </label>
          <label>{isEn?'Reasoning effort':'Mức suy luận'}
            <select className={inputClass} disabled={value.base_url !== 'https://openrouter.ai/api/v1'} title="OpenRouter" value={value.reasoning_effort || 'low'} onChange={event=>update({reasoning_effort:event.target.value as ModelConnectionInput['reasoning_effort']})}>
              <option value="none">{isEn?'Off (if supported)':'Tắt (nếu model hỗ trợ)'}</option>
              <option value="low">{isEn?'Low':'Thấp'}</option><option value="medium">{isEn?'Medium':'Vừa'}</option><option value="high">{isEn?'High':'Cao'}</option>
            </select>
          </label>
        </div>
      </details>
      <details className="text-xs text-zinc-600">
        <summary className="cursor-pointer">{isEn ? 'Estimated prices (optional)' : 'Đơn giá ước tính (tùy chọn)'}</summary>
        <p className="mt-2">{isEn ? 'Prices are your estimates, not a provider invoice.' : 'Giá do bạn khai báo, không phải hóa đơn nhà cung cấp.'}</p>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <label>{isEn ? 'Input USD / 1M tokens' : 'Đầu vào USD / 1 triệu token'}
            <input className={inputClass} type="number" min={0} max={1000} step="any" required
              value={value.input_price_per_million} onChange={event => update({ input_price_per_million: Number(event.target.value) })} />
          </label>
          <label>{isEn ? 'Output USD / 1M tokens' : 'Đầu ra USD / 1 triệu token'}
            <input className={inputClass} type="number" min={0} max={1000} step="any" required
              value={value.output_price_per_million} onChange={event => update({ output_price_per_million: Number(event.target.value) })} />
          </label>
        </div>
      </details>
    </>}
  </section>;
}
