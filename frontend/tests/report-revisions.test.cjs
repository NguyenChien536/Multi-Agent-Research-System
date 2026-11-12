const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/types/report-revisions.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);

test('numeric Markdown callbacks resolve to the API citation label without changing author-date references', () => {
  const label = context.exports.normalizeCitationLabel;
  const refs = [{ citation_label: '[1]', source_id: 'version-pinned-source' }];
  assert.equal(refs.find(item => item.citation_label === label('1'))?.source_id, 'version-pinned-source');
  assert.equal(label('[12]'), '[12]');
  assert.equal(label(' 12 '), '[12]');
  assert.equal(label('(Author, 2026)'), '(Author, 2026)');
});
