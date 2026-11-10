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

test('legacy invalid request is not mistaken for quota because of generic advice',()=>{
  const message=researchErrorText('Your API connection failed (OpenAIInvalidRequestError). Check its key, model, quota and supported output format.',true);
  assert.match(message,/rejected the request format/);
  assert.doesNotMatch(message,/Provider rate limit or quota reached/);
});

test('truncated output explains token exhaustion rather than rejected authentication', () => {
  assert.match(researchErrorText('LengthFinishReasonError', false), /không phải do API key/);
  assert.match(researchErrorText('MODEL_OUTPUT_TRUNCATED', true), /not an API-key error/);
});
test('authentication errors advise checking key and service address', () => {
  assert.match(researchErrorText('HTTP 401', false), /từ chối xác thực/);
  assert.match(researchErrorText('PROVIDER_AUTH_FAILED', true), /matching API address/);
});
test('overload and unavailable models have specific guidance without blaming a valid key', () => {
  assert.match(researchErrorText('PROVIDER_UNAVAILABLE: 503', true), /overloaded/);
  assert.match(researchErrorText('PROVIDER_UNAVAILABLE: 503', false), /không nhất thiết bị sai/);
  assert.match(researchErrorText('PROVIDER_MODEL_NOT_FOUND', true), /reload the model list/i);
  assert.match(researchErrorText('PROVIDER_MODEL_NOT_FOUND: The model is unavailable for this API connection.', true), /reload the model list/i);
  assert.match(researchErrorText('Gemini request queue is full', true), /rate limit/);
});
test('unknown and known errors never echo a credential from the provider body', () => {
  const secret = 'fake-test-key-never-real';
  for (const raw of ['Unexpected ' + secret, 'HTTP 401 ' + secret, 'LengthFinishReasonError ' + secret]) {
    assert.ok(!researchErrorText(raw, false).includes(secret));
    assert.ok(!researchErrorText(raw, true).includes(secret));
  }
});

test('invalid structured output does not assume an incompatible model or invalid key', () => {
  const en = researchErrorText('MODEL_INVALID_JSON: schema validation failed', true);
  const vi = researchErrorText('MODEL_INVALID_JSON: schema validation failed', false);
  assert.match(en, /did not match the required data structure/);
  assert.match(en, /does not by itself mean/);
  assert.match(en, /Continue from the failed step/);
  assert.match(vi, /không đồng nghĩa API key sai/);
  assert.match(vi, /JSON Schema/);
  assert.doesNotMatch(en, /Try a JSON-compatible model/);
  assert.match(researchErrorText('MODEL_OUTPUT_TRUNCATED: JSON response was cut off',true), /output token limit/);
});

test('active workflow time limit is distinct from provider timeout and output token limits', () => {
  assert.match(researchErrorText('TASK_TIME_LIMIT: active processing exhausted', true), /adding tokens does not add time/);
  assert.match(researchErrorText('TASK_TIME_LIMIT: active processing exhausted', false), /tăng token không tăng thời gian/);
  assert.match(researchErrorText('PROVIDER_TIMEOUT', true), /Provider response timed out/);
});
