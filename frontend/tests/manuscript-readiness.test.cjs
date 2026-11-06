const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const exports_ = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/components/research/ManuscriptReadiness.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText;
new Function('require', 'exports', code)(name => name === 'next/link'
  ? { __esModule: true, default: props => React.createElement('a', props) } : require(name), exports_);
const render = report => renderToStaticMarkup(React.createElement(exports_.ManuscriptReadiness, {
  report, taskId: 'task-1', isEn: true,
}));

test('readiness uses the saved version and collapses deduplicated review findings', () => {
  const html = render({ version_number: 2, review_status: 'NEEDS_REVIEW', review_metadata: {
    manuscript_findings: [{ message: 'More sources required.' }],
    bibliography_findings: ['More sources required.', '<script>unsafe</script>'],
  } });
  assert.ok(html.includes('Review needed'));
  assert.ok(html.includes('/research/task-1/revisions?version=2'));
  assert.ok(html.includes('View 2 review notes'));
  assert.ok(!html.includes('<details open'));
  assert.ok(!html.includes('<script>'));
});

test('missing review metadata or a budget limit never claims automated checks passed', () => {
  assert.ok(!render({}).includes('Automated checks passed'));
  assert.ok(!render({ review_status: 'PASSED', review_metadata: { budget_limited: true } }).includes('Automated checks passed'));
  assert.ok(render({ review_status: 'PASSED' }).includes('Automated checks passed'));
});

test('a recovered draft shows the review failure and never claims PASS', () => {
  const html = render({review_status: 'PASSED', review_metadata: {provider_limited: true,
    draft_recovery: {reason: 'MODEL_INVALID_JSON', review_incomplete: true}}});
  assert.ok(html.includes('valid review response'));
  assert.ok(html.includes('draft is saved; it has not passed review'));
  assert.ok(html.includes('/research/task-1/monitor#execution-errors'));
  assert.ok(!html.includes('Automated checks passed'));
});

test('unknown recovery reasons never expose raw provider text', () => {
  const html = render({review_status: 'NEEDS_REVIEW', review_metadata: {
    draft_recovery: {reason: 'private-provider-body-secret', review_incomplete: true}}});
  assert.ok(html.includes('review was interrupted'));
  assert.ok(!html.includes('private-provider-body-secret'));
});
