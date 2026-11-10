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
    label: 'OpenRouter',
    placeholder: 'openrouter/free',
  },
  'https://api.groq.com/openai/v1': {
    label: 'Groq',
    placeholder: 'llama-3.3-70b-versatile',
  },
  'https://generativelanguage.googleapis.com/v1beta/openai': {
    label: 'Google Gemini',
    placeholder: 'Select from the model list',
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
  const [modelNames, setModelNames] = useState<Record<string, string>>({});
  const [outputModes, setOutputModes] = useState<Record<string, ModelConnectionInput['structured_output_mode']>>({});
  const [outputLimits, setOutputLimits] = useState<Record<string, number>>({});
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogError, setCatalogError] = useState('');
  const [catalogChecked, setCatalogChecked] = useState(false);
  const [manualModel, setManualModel] = useState(false);
  const [freeOnly, setFreeOnly] = useState(true);
  const catalogRequest = useRef({sequence: 0});
  useEffect(() => {
    const tracker = catalogRequest.current;
    tracker.sequence++;
    setModels([]); setModelNames({}); setOutputModes({}); setSchemaModels({}); setOutputLimits({}); setCatalogChecked(false); setCatalogError(''); setCatalogBusy(false);
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
  const update = (patch: Partial<ModelConnectionInput>) => {
    if (!value) return;
    const next={...value,...patch};
    next.fallback_models=next.base_url==='https://openrouter.ai/api/v1' && next.input_price_per_million===0 && next.output_price_per_million===0 && (next.model.endsWith(':free') || next.model==='openrouter/free')
      ? (next.fallback_models || []).filter(name=>name!==next.model) : [];
    onChange(next);
  };
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
      setModelNames(Object.fromEntries(result.models.map(model => [model.id, model.display_name || model.id])));
      setOutputModes(Object.fromEntries(result.models.map(model => [model.id, model.recommended_output_mode || (model.supports_json_schema ? 'json_schema' : 'json_object')])));
      setOutputLimits(Object.fromEntries(result.models.filter(model => model.max_output_tokens).map(model => [model.id, model.max_output_tokens!])));
      setModels(names); setCatalogChecked(true); setManualModel(false);
      // Keep an explicit user choice. Never silently pick a paid model.
      const bestFree = result.models.filter(model => model.free && model.id.endsWith(':free') && model.max_output_tokens)
        .sort((a,b) => (b.max_output_tokens || 0) - (a.max_output_tokens || 0))[0];
      const selected = value.base_url === 'https://openrouter.ai/api/v1' && freeOnly && (!value.model || value.model === 'openrouter/free')
        ? bestFree : result.models.find(model => model.id === value.model);
      if (selected) update({model:selected.id, structured_output_mode:selected.recommended_output_mode || (selected.supports_json_schema ? 'json_schema' : 'json_object'),
        ...(selected.max_output_tokens ? {output_token_limit:selected.max_output_tokens} : {})});
    } catch (err) {
      if (request === catalogRequest.current.sequence) setCatalogError(err instanceof Error ? err.message : (isEn ? 'Unable to load models.' : 'Không tải được model.'));
    } finally { if (request === catalogRequest.current.sequence) setCatalogBusy(false); }
  }

  const handleBaseUrlChange = (newUrl: string) => {
    update({
      structured_output_mode: 'json_object',
      base_url: newUrl,
      fallback_models: [],
      api_key: '',
      model: newUrl === 'https://openrouter.ai/api/v1' ? 'openrouter/free' : '',
      input_price_per_million: 0,
      output_price_per_million: 0,
      output_token_limit: 32768,
    });
  };

  const activePlaceholder = (value?.base_url && KNOWN_PROVIDERS[value.base_url]?.placeholder)
    || (isEn ? 'Model ID from your provider' : 'Model ID do dịch vụ cung cấp');

  return <section className="space-y-3 border-t border-zinc-100 pt-4">
    {!hideToggle && <label className="flex items-center gap-2 text-sm font-semibold">
      <input type="checkbox" checked={!!value} onChange={event => onChange(event.target.checked ? {
        api_key: '', base_url: '', model: '', input_price_per_million: 0, output_price_per_million: 0, output_token_limit:32768,
      } : null)} />
      {isEn ? 'Use my API connection' : 'Dùng API key của tôi'}
    </label>}
    {value && <>
      {loadError && <div role="alert" className="flex items-center justify-between gap-2 text-sm text-red-700">
        <span>{isEn ? 'Could not load API services.' : 'Không tải được danh sách dịch vụ API.'}</span>
        <button type="button" onClick={() => setReload(value => value + 1)} className="underline">{isEn ? 'Retry' : 'Thử lại'}</button>
      </div>}
      <label className="block text-sm font-medium">{isEn ? '1. Service' : '1. Dịch vụ'}
        <select className={inputClass} required disabled={loading} value={value.base_url} onChange={event => handleBaseUrlChange(event.target.value)}>
          <option value="">{loading ? (isEn ? 'Loading services…' : 'Đang tải dịch vụ…') : (isEn ? 'Select API service' : 'Chọn dịch vụ API')}</option>
          {roots.map(root => (
            <option key={root} value={root}>
              {KNOWN_PROVIDERS[root]?.label || root}
            </option>
          ))}
        </select>
      </label>
      <div className="space-y-3">
        <label className="block text-sm font-medium">2. API key
          <input className={inputClass} type="password" required={keyRequired} minLength={8} maxLength={4096} autoComplete="off"
            placeholder={keyRequired ? '' : (isEn ? 'Saved securely · leave blank to keep' : 'Đã lưu an toàn · để trống để giữ key')}
            spellCheck={false} value={value.api_key} onChange={event => update({ api_key: event.target.value })} />
        </label>
        <div className="flex items-center gap-3">
          <button type="button" disabled={catalogBusy || !value.base_url || (keyRequired && !value.api_key)} onClick={loadModels}
            className="rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-40">{catalogBusy ? (isEn ? 'Loading…' : 'Đang tải…') : (isEn ? 'Load available models' : 'Tải danh sách model')}</button>
        </div>
        <label className="block text-sm font-medium">{isEn ? '3. Model' : '3. Model'}
          {!manualModel ? <select className={inputClass} required value={value.model} onChange={event => update({model:event.target.value, structured_output_mode:outputModes[event.target.value] || (schemaModels[event.target.value] ? 'json_schema' : 'json_object'),
            ...(outputLimits[event.target.value] ? {output_token_limit:outputLimits[event.target.value]} : {})})}>
            <option value="">{isEn ? 'Load models, then choose' : 'Tải danh sách rồi chọn model'}</option>
            {value.model && !models.includes(value.model) && <option value={value.model}>{value.model}</option>}
            {models.map(model => <option key={model} value={model}>{modelNames[model] || model}</option>)}
          </select> : <input className={inputClass} required maxLength={200} autoComplete="off" spellCheck={false}
            placeholder={activePlaceholder} value={value.model} onChange={event => update({model:event.target.value.trim(), structured_output_mode:'json_object'})} />}
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {['https://openrouter.ai/api/v1','https://generativelanguage.googleapis.com/v1beta/openai'].includes(value.base_url) && <label className="flex items-center gap-1"><input type="checkbox" checked={freeOnly} onChange={event=>setFreeOnly(event.target.checked)} />{isEn ? 'Models with a free tier' : 'Model có gói miễn phí'}</label>}
      </div>
      {catalogError && <p role="alert" className="text-sm text-red-700">{catalogError}</p>}
      {catalogChecked && <p role="status" className="text-xs text-zinc-600">{isEn ? 'List loaded. Use Check response to test the selected model.' : 'Đã tải danh sách. Bấm Thử phản hồi để kiểm tra model đã chọn.'}</p>}
      {value.base_url === 'https://openrouter.ai/api/v1' && value.input_price_per_million === 0 && value.output_price_per_million === 0 && <details className="rounded-lg border border-zinc-200 p-3 text-sm">
        <summary className="cursor-pointer font-medium">{isEn ? 'Free fallback models' : 'Model miễn phí dự phòng'}{value.fallback_models?.length ? ` (${value.fallback_models.length}/3)` : ''}</summary>
        <p className="mt-2 text-xs text-zinc-600">{isEn ? 'Choose up to 3 backups, in order. OpenRouter tries them if the primary is unavailable. A shared daily quota still requires waiting.' : 'Chọn tối đa 3 model theo thứ tự dự phòng. OpenRouter thử khi model chính không khả dụng. Hết quota chung vẫn phải chờ.'}</p>
        {!catalogChecked && <p className="mt-2 text-xs">{isEn ? 'Load models to see compatible options.' : 'Tải danh sách để xem các lựa chọn tương thích.'}</p>}
        {Array.from(new Set([...(value.fallback_models || []),...models.filter(name=>name.endsWith(':free') && schemaModels[name])])).filter(name=>name!==value.model).map(name=>{
          const selected=(value.fallback_models || []).includes(name);
          return <label key={name} className="mt-2 flex items-start gap-2 break-all text-xs">
            <input type="checkbox" checked={selected} disabled={!selected && (value.fallback_models?.length || 0)>=3} onChange={()=>update({fallback_models:selected ? (value.fallback_models || []).filter(id=>id!==name) : [...(value.fallback_models || []),name]})} />
            <span>{selected ? `${(value.fallback_models || []).indexOf(name)+1}. ` : ''}{modelNames[name] || name}</span>
          </label>;
        })}
      </details>}
      {catalogChecked && value.model && !models.includes(value.model) && <p role="alert" className="text-sm text-amber-700">{isEn ? 'This model was not found. Choose a model from the list or check its exact ID in Advanced.' : 'Không tìm thấy model này. Chọn từ danh sách hoặc kiểm tra tên chính xác trong phần Nâng cao.'}</p>}
      <details className="text-sm text-zinc-700">
        <summary className="cursor-pointer">{isEn ? 'Advanced' : 'Nâng cao'}</summary>
        <p className="mt-2 break-all text-xs text-zinc-500">API: {value.base_url}</p>
        <button type="button" className="mt-2 text-xs underline" onClick={()=>setManualModel(v=>!v)}>{manualModel ? (isEn ? 'Choose from list' : 'Chọn từ danh sách') : (isEn ? 'Enter model ID manually' : 'Nhập tên model thủ công')}</button>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <label>{isEn ? 'Structured data compatibility' : 'Tương thích dữ liệu có cấu trúc'}
            <select className={inputClass} value={value.structured_output_mode || 'json_object'} onChange={event=>update({structured_output_mode:event.target.value as ModelConnectionInput['structured_output_mode']})}>
              <option value="json_object">{isEn ? 'JSON · broad compatibility' : 'JSON · tương thích rộng'}</option>
              <option value="json_schema">{isEn ? 'JSON Schema · supported endpoints' : 'JSON Schema · endpoint có hỗ trợ'}</option>
              <option value="prompt_json">{isEn ? 'Prompt JSON · local validation' : 'JSON bằng chỉ dẫn · kiểm tra tại hệ thống'}</option>
            </select>
          </label>
          <label>{isEn?'Output token limit':'Giới hạn token đầu ra'}
            <input type="number" min={1024} max={outputLimits[value.model] || 1000000} step={1} required className={inputClass}
              value={value.output_token_limit || 32768} onChange={event=>update({output_token_limit:Number(event.target.value)})} />
            {outputLimits[value.model] && <button type="button" className="mt-1 text-xs underline" onClick={()=>update({output_token_limit:outputLimits[value.model]})}>
              {isEn ? 'Use model maximum' : 'Dùng mức tối đa của model'} ({outputLimits[value.model].toLocaleString()})
            </button>}
          </label>
          <label>{isEn?'Reasoning effort':'Mức suy luận'}
            <select className={inputClass} disabled={!['https://openrouter.ai/api/v1','https://generativelanguage.googleapis.com/v1beta/openai'].includes(value.base_url)} value={value.reasoning_effort || 'low'} onChange={event=>update({reasoning_effort:event.target.value as ModelConnectionInput['reasoning_effort']})}>
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
