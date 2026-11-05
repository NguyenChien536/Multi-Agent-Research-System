const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/page.tsx'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
} }).outputText;
const saved = { connection: { model: 'test/free-model', has_key: true } };

async function home({ initial = 'pending', connection = saved, signedIn = true, serverMode = false } = {}) {
  const states = [], effects = [], dependencies = [], routes = [], created = [], started = [];
  const storage = new Map();
  let cursor = 0, calls = 0;
  const window = new EventTarget();
  const sessionStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
  const hooks = {
    useState: initial => {
      const index = cursor++;
      if (!(index in states)) states[index] = initial;
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }];
    },
    useEffect: (callback, deps) => {
      const index = cursor++;
      if (!dependencies[index] || deps.some((value, i) => value !== dependencies[index][i])) {
        dependencies[index] = deps;
        effects.push(callback);
      }
    },
  };
  const api = {
    auth: { hasSession: () => signedIn, me: async () => ({ username: 'owner', email: 'owner@example.com' }) },
    settings: { getModelConnection: async () => {
      calls++;
      if (calls === 1 && initial === 'pending') return new Promise(() => {});
      if (calls === 1 && initial === 'failed') throw new Error('initial network failure');
      if (connection instanceof Error) throw connection;
      return connection;
    } },
    tasks: { modelConnectionOptions: async () => ({ use_server_providers: serverMode, server_provider_ready: true, server_provider: 'gemini' }), create: async value => { created.push(value); return { id: 'new-research' }; },
      start: async id => { started.push(id); }, uploadPdf: async () => {} },
  };
  const context = { exports: {}, window, sessionStorage, require: name => {
    if (name === 'react') return hooks;
    if (name === 'react/jsx-runtime') return require(name);
    if (name === 'next/navigation') return { useRouter: () => ({ push: route => routes.push(route) }) };
    if (name === '@/lib/api') return { api };
    if (name === '@/lib/i18n') return { useLanguage: () => ({ language: 'en', setLanguage() {}, t: key => key }) };
    if (name === '@/components/ui/Button') return { Button: 'button' };
    if (name === '@/components/ModelSettingsPanel') return { ModelSettingsPanel: 'model-settings-panel' };
    if (name === 'lucide-react') return new Proxy({}, { get: (_, key) => key });
    throw new Error('Unexpected import: ' + name);
  } };
  vm.runInNewContext(compiled, context);
  function render() { cursor = 0; return context.exports.default(); }
  render();
  while (effects.length) effects.shift()();
  await new Promise(resolve => setImmediate(resolve));
  const question = 'What evidence explains differences in learning outcomes?';
  elements(render()).find(node => node.type === 'textarea').props.onChange({ target: { value: question } });
  return { render, routes, created, started, question, storage };
}

function elements(node) {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node, ...elements(node.props?.children)];
}
function text(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node !== 'object') return String(node);
  if (Array.isArray(node)) return node.map(text).join('');
  return text(node.props?.children);
}
function submit(h) { return elements(h.render()).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} }); }

for (const initial of ['pending', 'failed']) {
  test(`start rechecks saved settings when the initial summary is ${initial}`, async () => {
    const h = await home({ initial });
    await submit(h);
    assert.equal(h.created.length, 1);
    assert.equal(h.created[0].research_question, h.question);
    assert.deepEqual(h.started, ['new-research']);
    assert.deepEqual(h.routes, ['/research/new-research']);
  });
}

for (const connection of [{ connection: null }, { connection: { model: 'revoked', has_key: false } }]) {
  test('missing saved credentials preserve the question without navigation or provider work', async () => {
    const h = await home({ connection });
    await submit(h);
    assert.equal(h.created.length, 0);
    assert.equal(h.started.length, 0);
    assert.equal(h.routes.length, 0);
    assert.equal(elements(h.render()).find(node => node.type === 'textarea').props.value, h.question);
    assert.ok(text(h.render()).includes('No default API/model is saved'));
    const open = elements(h.render()).find(node => node.type === 'button' && text(node) === 'API & model');
    open.props.onClick();
    assert.ok(elements(h.render()).some(node => node.props?.role === 'dialog'));
    assert.equal(h.routes.length, 0);
  });
}

test('a settings network error is not treated as missing credentials or redirected to Settings', async () => {
  const h = await home({ connection: new Error('unavailable') });
  await submit(h);
  assert.equal(h.routes.length, 0);
  assert.equal(h.created.length, 0);
  assert.ok(text(h.render()).includes('Unable to check your saved API connection'));
});

test('a signed-out visitor is sent only to login and keeps the research draft', async () => {
  const h = await home({ signedIn: false });
  await submit(h);
  assert.deepEqual(h.routes, ['/login?next=%2F']);
  assert.equal(JSON.parse(h.storage.get('synthia_draft_research')).topic, h.question);
  assert.equal(h.created.length, 0);
});

for (const [label, kind] of [['Computational Empirical', 'EMPIRICAL_COMPUTATIONAL'], ['Fieldwork / User Data', 'EMPIRICAL_HUMAN']]) {
  test(`saved model starts the selected ${kind} path without a Settings redirect`, async () => {
    const h = await home();
    elements(h.render()).find(node => node.type === 'button' && text(node).includes(label)).props.onClick();
    await submit(h);
    assert.equal(h.created[0].research_type, kind);
    assert.deepEqual(h.started, ['new-research']);
    assert.deepEqual(h.routes, ['/research/new-research']);
  });
}

test('missing configuration and opening its dialog keep the selected PDF in the draft', async () => {
  const h = await home({ connection: { connection: null } });
  elements(h.render()).find(node => node.type === 'button' && text(node).includes('Configuration')).props.onClick();
  const upload = elements(h.render()).find(node => node.type === 'input' && node.props.type === 'file');
  upload.props.onChange({ target: { files: [{ name: 'retained-source.pdf', type: 'application/pdf', size: 100 }], value: 'file' } });
  await submit(h);
  assert.ok(text(h.render()).includes('retained-source.pdf'));
  elements(h.render()).find(node => node.type === 'button' && text(node) === 'API & model').props.onClick();
  assert.ok(text(h.render()).includes('retained-source.pdf'));
  assert.equal(h.created.length, 0);
  assert.equal(h.routes.length, 0);
});


test('server env mode starts when no personal connection is saved', async () => {
  const h = await home({ serverMode: true, connection: { connection: null } });
  await submit(h);
  assert.equal(h.created.length, 1);
  assert.equal(h.created[0].use_saved_connection, false);
  assert.deepEqual(h.routes, ['/research/new-research']);
});

test('a saved personal connection takes priority over the server default', async () => {
  const h = await home({ serverMode: true });
  await submit(h);
  assert.equal(h.created[0].use_saved_connection, true);
  assert.deepEqual(h.routes, ['/research/new-research']);
});
