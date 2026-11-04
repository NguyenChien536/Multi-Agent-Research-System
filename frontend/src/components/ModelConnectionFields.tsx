'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ModelConnectionInput } from '@/types';

interface ProviderMeta {
  label: string;
  defaultModel: string;
  placeholder: string;
}

const KNOWN_PROVIDERS: Record<string, ProviderMeta> = {
  'https://openrouter.ai/api/v1': {
    label: 'OpenRouter (openrouter.ai)',
    defaultModel: 'meta-llama/llama-3.3-70b-instruct:free',
    placeholder: 'meta-llama/llama-3.3-70b-instruct:free',
  },
  'https://api.groq.com/openai/v1': {
    label: 'Groq Cloud (api.groq.com)',
    defaultModel: 'llama-3.3-70b-versatile',
    placeholder: 'llama-3.3-70b-versatile',
  },
  'https://generativelanguage.googleapis.com/v1beta/openai': {
    label: 'Google Gemini (OpenAI-compatible)',
    defaultModel: 'gemini-2.5-flash',
    placeholder: 'gemini-2.5-flash',
  },
  'https://api.deepseek.com/v1': {
    label: 'DeepSeek (api.deepseek.com)',
    defaultModel: 'deepseek-chat',
    placeholder: 'deepseek-chat',
  },
  'https://api.mistral.ai/v1': {
    label: 'Mistral AI (api.mistral.ai)',
    defaultModel: 'mistral-small-latest',
    placeholder: 'mistral-small-latest',
  },
  'https://api.openai.com/v1': {
    label: 'OpenAI (api.openai.com)',
    defaultModel: 'gpt-4o-mini',
    placeholder: 'gpt-4o-mini',
  },
  'https://api.together.xyz/v1': {
    label: 'Together AI (api.together.xyz)',
    defaultModel: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
    placeholder: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
  },
  'https://api.cerebras.ai/v1': {
    label: 'Cerebras (api.cerebras.ai)',
    defaultModel: 'llama3.1-70b',
    placeholder: 'llama3.1-70b',
  },
};

export function ModelConnectionFields({ value, onChange, isEn }: {
  value: ModelConnectionInput | null;
  onChange: (value: ModelConnectionInput | null) => void;
  isEn: boolean;
}) {
  const [roots, setRoots] = useState<string[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
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

  const handleBaseUrlChange = (newUrl: string) => {
    update({
      base_url: newUrl,
      api_key: '',
      model: newUrl === 'https://openrouter.ai/api/v1' ? 'openrouter/free' : '',
    });
  };

  const activePlaceholder = (value?.base_url && KNOWN_PROVIDERS[value.base_url]?.placeholder)
    || (isEn ? 'Model ID from your provider' : 'Model ID do dịch vụ cung cấp');

  return <section className="space-y-3 border-t border-zinc-100 pt-4">
    <label className="flex items-center gap-2 text-sm font-semibold">
      <input type="checkbox" checked={!!value} onChange={event => onChange(event.target.checked ? {
        api_key: '', base_url: '', model: '', input_price_per_million: 0, output_price_per_million: 0,
      } : null)} />
      {isEn ? 'Use my API connection' : 'Dùng API key của tôi'}
    </label>
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
          <input className={inputClass} type="password" required minLength={8} maxLength={4096} autoComplete="off"
            spellCheck={false} value={value.api_key} onChange={event => update({ api_key: event.target.value })} />
        </label>
        <label className="block text-xs font-medium">{isEn ? 'Exact model ID' : 'Tên model chính xác'}
          <input className={inputClass} required maxLength={200} autoComplete="off" spellCheck={false}
            placeholder={activePlaceholder}
            value={value.model} onChange={event => update({ model: event.target.value.trim() })} />
        </label>
      </div>
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
