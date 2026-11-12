const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/report-questions.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;
const context = { exports: {}, URL };
vm.runInNewContext(compiled, context);

test('question references allow public HTTP links but never scripts, private storage or embedded credentials', () => {
  const safe = context.exports.safeSourceUrl;
  assert.equal(safe('https://example.com/paper'), 'https://example.com/paper');
  assert.equal(safe('http://example.com/paper'), 'http://example.com/paper');
  for (const value of ['javascript:alert(1)', 'data:text/html,secret', 'file:///private.pdf',
    'upload://private/document.pdf', '/storage/private.pdf', 'https://user:secret@example.com']) {
    assert.equal(safe(value), null);
  }
});

test('failed verification and insufficient evidence have different user messages', () => {
  assert.equal(context.exports.QUESTION_STATUS.INSUFFICIENT_EVIDENCE, 'Chưa đủ bằng chứng');
  assert.match(context.exports.QUESTION_ERRORS.INVALID_REFERENCE, /chưa xác minh/);
  assert.match(context.exports.QUESTION_ERRORS.BUDGET_LIMIT, /giới hạn tài nguyên AI/);
});
