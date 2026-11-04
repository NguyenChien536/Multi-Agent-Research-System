const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/components/ResearchErrorNotice.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const mod = new Module(filename, module);
mod.filename = filename;
mod.paths = Module._nodeModulePaths(path.dirname(filename));
mod._compile(compiled, filename);
const { researchErrorText } = mod.exports;

test('truncated output explains token exhaustion rather than rejected authentication', () => {
  assert.match(researchErrorText('LengthFinishReasonError', false), /không phải do API key/);
  assert.match(researchErrorText('MODEL_OUTPUT_TRUNCATED', true), /not an API-key error/);
});
test('authentication errors advise checking key and service address', () => {
  assert.match(researchErrorText('HTTP 401', false), /từ chối xác thực/);
  assert.match(researchErrorText('PROVIDER_AUTH_FAILED', true), /matching API address/);
});
test('unknown and known errors never echo a credential from the provider body', () => {
  const secret = 'fake-test-key-never-real';
  for (const raw of ['Unexpected ' + secret, 'HTTP 401 ' + secret, 'LengthFinishReasonError ' + secret]) {
    assert.ok(!researchErrorText(raw, false).includes(secret));
    assert.ok(!researchErrorText(raw, true).includes(secret));
  }
});
