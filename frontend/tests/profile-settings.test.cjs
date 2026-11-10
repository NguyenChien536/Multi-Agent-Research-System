const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// Execute the real form handlers with controlled hooks and API responses.
// No browser storage or real account is used by these interaction checks.
const source = fs.readFileSync(path.join(__dirname, '../src/components/ProfileSettingsPanel.tsx'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
} }).outputText;

async function panel() {
  const original = { id: 'owner', full_name: 'Original Name', username: 'original', email: 'owner@example.com' };
  const states = [], effects = [], dependencies = [], updates = [], deletions = [], redirects = [];
  let cursor = 0, loggedOut = false;
  const window = new EventTarget();
  const hooks = {
    useId: () => 'profile-test',
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
  const api = { auth: {
    me: async () => ({ ...original }),
    updateProfile: async value => { updates.push(value); return { ...original, ...value }; },
    deleteAccount: async value => { deletions.push(value); return { status: 'DELETING' }; },
    logout: () => { loggedOut = true; },
  } };
  const context = { exports: {}, window, CustomEvent, require: name => {
    if (name === 'react') return hooks;
    if (name === 'react/jsx-runtime') return require(name);
    if (name === 'next/navigation') return { useRouter: () => ({ replace: url => redirects.push(url) }) };
    if (name === '@/lib/api') return { api, APIError: class extends Error {} };
    throw new Error('Unexpected module: ' + name);
  } };
  vm.runInNewContext(compiled, context);
  function render() { cursor = 0; return context.exports.ProfileSettingsPanel({ isEn: true }); }
  render();
  while (effects.length) effects.shift()();
  await new Promise(resolve => setImmediate(resolve));
  return { render, updates, deletions, redirects, loggedOut: () => loggedOut };
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
function button(tree, label) { return elements(tree).find(node => node.type === 'button' && text(node) === label); }
function input(tree, name) { return elements(tree).find(node => node.type === 'input' && node.props.name === name); }
function form(tree) { return elements(tree).find(node => node.type === 'form'); }
const change = (field, value) => field.props.onChange({ target: { value } });

test('profile is read-only until Edit; Cancel discards drafts without a request', async () => {
  const p = await panel();
  assert.equal(elements(p.render()).filter(node => node.type === 'input').length, 0);
  button(p.render(), 'Edit').props.onClick();
  change(input(p.render(), 'full_name'), 'Unsaved Name');
  button(p.render(), 'Cancel').props.onClick();
  assert.ok(text(p.render()).includes('Original Name'));
  assert.ok(!text(p.render()).includes('Unsaved Name'));
  assert.equal(p.updates.length, 0);
  assert.equal(elements(p.render()).filter(node => node.type === 'input').length, 0);
});

test('only Save sends edited values and successful save returns to read-only view', async () => {
  const p = await panel();
  button(p.render(), 'Edit').props.onClick();
  change(input(p.render(), 'full_name'), 'Updated Name');
  assert.equal(p.updates.length, 0);
  await form(p.render()).props.onSubmit({ preventDefault() {} });
  assert.equal(p.updates.length, 1);
  assert.equal(p.updates[0].full_name, 'Updated Name');
  assert.ok(text(p.render()).includes('Updated Name'));
  assert.ok(button(p.render(), 'Edit'));
});

test('delete disclosure and Cancel do not delete or sign out the account', async () => {
  const p = await panel();
  button(p.render(), 'Delete account').props.onClick();
  assert.ok(button(p.render(), 'Permanently delete account').props.disabled);
  await form(p.render()).props.onSubmit({ preventDefault() {} });
  assert.equal(p.deletions.length, 0);
  button(p.render(), 'Cancel').props.onClick();
  assert.ok(button(p.render(), 'Edit'));
  assert.equal(p.loggedOut(), false);
});

test('confirmed deletion requires password and DELETE, then signs out after acceptance', async () => {
  const p = await panel();
  button(p.render(), 'Delete account').props.onClick();
  change(input(p.render(), 'delete_password'), 'fake-password');
  change(input(p.render(), 'confirmation'), 'DELETE');
  assert.equal(button(p.render(), 'Permanently delete account').props.disabled, false);
  assert.equal(p.deletions.length, 0);
  await form(p.render()).props.onSubmit({ preventDefault() {} });
  assert.equal(p.deletions.length, 1);
  assert.equal(p.deletions[0].confirmation, 'DELETE');
  assert.equal(p.loggedOut(), true);
  assert.deepEqual(p.redirects, ['/login?account=deleted']);
});
