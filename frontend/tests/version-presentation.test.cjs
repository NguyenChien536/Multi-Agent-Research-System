const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/versionPresentation.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;
const exported = {};
new Function('require', 'exports', compiled)(require, exported);

test('revision metadata labels identify versions without inventing a DOI', () => {
  assert.equal(exported.formatVersionLabel(3, 'NEEDS_REVIEW', true), 'Version v3 · Review needed');
  assert.equal(exported.formatVersionLabel(3, 'NEEDS_REVIEW', false), 'Phiên bản v3 · Cần kiểm tra');
  assert.equal(exported.formatVersionLabel(undefined, undefined, true), 'Version unavailable · Review status unavailable');
  assert.equal(exported.formatVersionLabel(undefined, undefined, false), 'Chưa có số phiên bản · Chưa có kết quả kiểm tra');
  assert.equal(exported.formatReviewStatus('UNKNOWN', true), 'Review status unavailable');
  assert.equal(exported.formatReviewStatus('PASSED', true), 'Automated checks passed');
  assert.ok(!source.includes('10.synthia'));
});
