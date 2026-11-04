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
  useEffect(() => {
    if (!api.auth.hasSession()) { setLoadError(true); return; }
    let active = true;
    api.tasks.modelConnectionOptions().then(result => {
      if (active) setRoots(result.base_urls);
    }).catch(() => { if (active) setLoadError(true); });
    return () => { active = false; };
  }, []);
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
      <p className="text-xs text-zinc-500">{isEn
        ? 'Connect a service that supports the OpenAI-compatible chat format. This does not require an OpenAI account.'
        : 'Kết nối dịch vụ hỗ trợ định dạng chat tương thích OpenAI. Không bắt buộc dùng dịch vụ của OpenAI.'}</p>
      {loadError && <p role="alert" className="text-xs text-red-600">{isEn ? 'Sign in and reload to load trusted API addresses.' : 'Đăng nhập và tải lại trang để lấy danh sách địa chỉ API.'}</p>}
      <label className="block text-xs font-medium">{isEn ? 'API base URL' : 'Địa chỉ API (base URL)'}
        <select className={inputClass} required value={value.base_url} onChange={event => handleBaseUrlChange(event.target.value)}>
          <option value="">{isEn ? 'Select your service address' : 'Chọn địa chỉ dịch vụ bạn dùng'}</option>
          {roots.map(root => (
            <option key={root} value={root}>
              {KNOWN_PROVIDERS[root]?.label ? `${KNOWN_PROVIDERS[root].label} (${root})` : root}
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
        <summary className="cursor-pointer">{isEn ? 'Estimated token prices (default: free tier)' : 'Đơn giá ước tính (mặc định: gói miễn phí)'}</summary>
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
      <p className="text-xs leading-relaxed text-zinc-500">{isEn
        ? 'The key is encrypted for this research, not saved in browser drafts. No automatic fallback to server keys. Discovery uses public scholarly indexes and lexical retrieval. Zero is your declared price; actual billing and free quota depend on your provider.'
        : 'Key được mã hóa riêng cho bài này, không lưu trong bản nháp trình duyệt. Không tự chuyển sang key máy chủ. Tìm nguồn bằng chỉ mục học thuật công khai và truy xuất từ khóa. Giá 0 do bạn khai báo; phí thực tế và hạn mức miễn phí phụ thuộc dịch vụ.'}</p>
      {value.base_url === 'https://openrouter.ai/api/v1' && !value.input_price_per_million && !value.output_price_per_million &&
        <p className="text-xs text-zinc-600">{isEn ? 'Select a model ending in :free or openrouter/free. Paid routing is blocked.' : 'Chọn model có đuôi :free hoặc openrouter/free. Chặn định tuyến sang model trả phí.'}</p>}
    </>}
  </section>;
}
