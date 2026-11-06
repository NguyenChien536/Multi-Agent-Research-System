const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;

function client({ status = 200, response = {}, token = 'test-token' } = {}) {
  const storage = new Map(token ? [['synthia_access_token', token]] : []);
  const requests = [], redirects = [];
  const context = { exports: {}, process: { env: {} }, Headers, FormData,
    window: {
      sessionStorage: { getItem: key => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
      location: { pathname: '/research/example', search: '?tab=report', assign: url => redirects.push(url) },
    },
    fetch: async (url, config) => {
      requests.push({ url, ...config });
      return { ok: status < 400, status, json: async () => response, blob: async () => response };
    },
  };
  vm.runInNewContext(compiled, context);
  return { api: context.exports.api, requests, storage, redirects };
}

test('protected auth/me and task requests both include the session token', async () => {
  const c = client();
  await c.api.auth.me();
  await c.api.tasks.list();
  assert.equal(c.requests.length, 2);
  for (const request of c.requests) assert.equal(request.headers.get('Authorization'), 'Bearer test-token');
});

test('retry uses its owning article and preserves the session', async () => {
  const c=client();
  await c.api.tasks.retry('failed-article');
  assert.ok(c.requests[0].url.endsWith('/research/failed-article/retry'));
  assert.equal(c.requests[0].method,'POST');
  assert.equal(c.requests[0].headers.get('Authorization'),'Bearer test-token');
});

test('model discovery sends credentials only in the authenticated POST body',async()=>{
  const c=client();
  const payload={base_url:'https://api.groq.com/openai/v1',api_key:'fake-catalog-key',task_id:'owned-task'};
  await c.api.settings.discoverModels(payload);
  assert.ok(c.requests[0].url.endsWith('/settings/model-connection/models'));
  assert.ok(!c.requests[0].url.includes(payload.api_key));
  assert.equal(c.requests[0].method,'POST');
  assert.equal(c.requests[0].headers.get('Authorization'),'Bearer test-token');
  assert.deepEqual(JSON.parse(c.requests[0].body),payload);
});

test('dataset upload shares session expiry handling', async()=>{
  const c=client({status:401,response:{detail:'Session expired'}});
  await assert.rejects(c.api.tasks.uploadDataset('owned-task',new Blob(['target\n1'])));
  assert.ok(c.requests[0].url.endsWith('/research/owned-task/dataset'));
  assert.ok(c.requests[0].body instanceof FormData);
  assert.equal(c.storage.get('synthia_access_token'),undefined);
  assert.equal(c.redirects.length,1);
});

test('profile edits use the authenticated current-user route and preserve the session', async () => {
  const updated = { id: 'owner-id', username: 'new-name', email: 'new@example.com', full_name: 'New Name' };
  const c = client({ response: updated });
  const payload = { email: 'new@example.com', current_password: 'fake-current-password' };
  assert.equal(await c.api.auth.updateProfile(payload), updated);
  assert.ok(c.requests[0].url.endsWith('/auth/me'));
  assert.equal(c.requests[0].method, 'PATCH');
  assert.equal(c.requests[0].headers.get('Authorization'), 'Bearer test-token');
  assert.deepEqual(JSON.parse(c.requests[0].body), payload);
  assert.equal(c.storage.get('synthia_access_token'), 'test-token');
});

test('saved model checks are authenticated and never reuse a cached profile', async () => {
  const c = client({ response: { connection: { model: 'free-model', has_key: true } } });
  assert.equal((await c.api.settings.getModelConnection()).connection.model, 'free-model');
  assert.ok(c.requests[0].url.endsWith('/settings/model-connection'));
  assert.equal(c.requests[0].headers.get('Authorization'), 'Bearer test-token');
  assert.equal(c.requests[0].cache, 'no-store');
});

test('profile conflicts keep the current session and expose the server status', async () => {
  const c = client({ status: 409, response: { detail: 'Already registered' } });
  await assert.rejects(c.api.auth.updateProfile({ username: 'taken' }), error => error.status === 409);
  assert.equal(c.storage.get('synthia_access_token'), 'test-token');
  assert.equal(c.redirects.length, 0);
});

test('account deletion sends explicit confirmation and password on the authenticated self route', async () => {
  const c = client({ response: { status: 'DELETING' } });
  const payload = { current_password: 'fake-password', confirmation: 'DELETE' };
  assert.equal((await c.api.auth.deleteAccount(payload)).status, 'DELETING');
  assert.ok(c.requests[0].url.endsWith('/auth/me'));
  assert.equal(c.requests[0].method, 'DELETE');
  assert.equal(c.requests[0].headers.get('Authorization'), 'Bearer test-token');
  assert.deepEqual(JSON.parse(c.requests[0].body), payload);
});

test('artifact downloads use shared authenticated binary handling and expire sessions consistently', async () => {
  const blob = new Blob(['private artifact']);
  const c = client({response: blob});
  assert.equal(await c.api.tasks.downloadArtifact('paper', 'artifact'), blob);
  assert.ok(c.requests[0].url.endsWith('/research/paper/artifacts/artifact/download'));
  assert.equal(c.requests[0].headers.get('Authorization'), 'Bearer test-token');
  assert.equal(c.requests[0].cache, 'no-store');
  const expired = client({status: 401});
  await assert.rejects(expired.api.tasks.downloadArtifact('paper', 'artifact'));
  assert.equal(expired.storage.size, 0);
  assert.equal(expired.redirects.length, 1);
});

test('experiment downloads pin version, keep binary data, disable cache and include auth/abort', async () => {
  const blob = new Blob(['private zip bytes']);
  const c = client({ response: blob });
  const controller = new AbortController();
  assert.equal(await c.api.tasks.getExperimentBundle('paper', 3, controller.signal), blob);
  const request = c.requests[0];
  assert.ok(request.url.endsWith('/research/paper/report/versions/3/experiment-bundle'));
  assert.equal(request.headers.get('Authorization'), 'Bearer test-token');
  assert.equal(request.cache, 'no-store');
  assert.equal(request.signal, controller.signal);
});

test('experiment export expiry uses the shared session-expired behavior', async () => {
  const c = client({ status: 401, response: { detail: 'expired' } });
  await assert.rejects(c.api.tasks.getExperimentBundle('paper', 1), error => error.status === 401);
  assert.equal(c.storage.has('synthia_access_token'), false);
  assert.equal(c.redirects.length, 1);
});

test('experiment availability requests preserve report version and server reason', async () => {
  const c = client({ response: { available: false, computational: true, reason: 'Missing historical snapshot' } });
  const data = await c.api.tasks.getExperimentBundleAvailability('paper', 2);
  assert.ok(c.requests[0].url.endsWith('/research/paper/report/versions/2/experiment-bundle/availability'));
  assert.equal(data.reason, 'Missing historical snapshot');
});

test('login/register are public; successful login replaces the session', async () => {
  const c = client({ response: { access_token: 'new-token' } });
  await c.api.auth.register({ username: 'example' });
  await c.api.auth.login('example@example.com', 'password');
  for (const request of c.requests) assert.equal(request.headers.has('Authorization'), false);
  assert.equal(c.storage.get('synthia_access_token'), 'new-token');
});

test('expired profile session is cleared and returns to login with a relative next path', async () => {
  const c = client({ status: 401, response: { detail: 'expired' } });
  await assert.rejects(c.api.auth.me(), error => error.status === 401);
  assert.equal(c.storage.has('synthia_access_token'), false);
  assert.deepEqual(c.redirects, ['/login?next=%2Fresearch%2Fexample%3Ftab%3Dreport']);
});

test('failed public login does not redirect or clear an unrelated stored session', async () => {
  const c = client({ status: 401, response: { detail: 'bad credentials' } });
  await assert.rejects(c.api.auth.login('email', 'bad'), error => error.status === 401);
  assert.equal(c.redirects.length, 0);
  assert.equal(c.storage.get('synthia_access_token'), 'test-token');
});

test('fieldwork upload uses authenticated multipart and shares expiry handling', async () => {
  const c = client({ status: 401 });
  await assert.rejects(c.api.tasks.uploadFieldworkResult('task', new Blob(['result'])), error => error.status === 401);
  assert.equal(c.requests[0].headers.get('Authorization'), 'Bearer test-token');
  assert.equal(c.requests[0].headers.has('Content-Type'), false);
  assert.ok(c.requests[0].body instanceof FormData);
  assert.equal(c.redirects.length, 1);
});

test('monitoring requests carry auth, pagination, cancellation and disable response caching', async () => {
  const c = client();
  const controller = new AbortController();
  await c.api.tasks.getMonitor('paper-id', 20, 20, controller.signal);
  const request = c.requests[0];
  assert.ok(request.url.endsWith('/research/paper-id/monitor?offset=20&limit=20'));
  assert.equal(request.headers.get('Authorization'), 'Bearer test-token');
  assert.equal(request.signal, controller.signal);
  assert.equal(request.cache, 'no-store');
});

test('question requests pin the explicit report version and preserve the idempotency key', async () => {
  const c = client();
  const payload = { request_id: 'stable-request-id', question: 'What supports this conclusion?' };
  await c.api.tasks.askQuestion('paper-id', 1, payload);
  await c.api.tasks.getQuestionHistory('paper-id', 1, 20);
  assert.ok(c.requests[0].url.endsWith('/research/paper-id/report/versions/1/questions'));
  assert.deepEqual(JSON.parse(c.requests[0].body), payload);
  assert.equal(c.requests[0].headers.get('Authorization'), 'Bearer test-token');
  assert.ok(c.requests[1].url.endsWith('/research/paper-id/report/versions/1/questions?offset=20&limit=20'));
  assert.equal(c.requests[1].cache, 'no-store');
});

test('publication exports pin version/template and use authenticated noncached requests', async () => {
  const c = client();
  await c.api.tasks.getPublication('paper-id', 2, 'IEEE_CONFERENCE');
  const request = c.requests[0];
  assert.ok(request.url.endsWith('/research/paper-id/report/versions/2/publication?template=IEEE_CONFERENCE'));
  assert.equal(request.headers.get('Authorization'), 'Bearer test-token');
  assert.equal(request.cache, 'no-store');
});

test('editorial revisions preserve base version, request UUID, auth and abort signal', async () => {
  const c = client();
  const controller = new AbortController();
  const payload = { request_id: 'stable-revision-id', instructions: 'Clarify the original discussion.' };
  await c.api.tasks.reviseReport('paper-id', 3, payload, controller.signal);
  await c.api.tasks.getRevisionHistory('paper-id', 3, controller.signal);
  await c.api.tasks.getReportVersion('paper-id', 3, controller.signal);
  await c.api.tasks.getReportVersionCitations('paper-id', 3, controller.signal);
  assert.ok(c.requests[0].url.endsWith('/report/versions/3/revisions'));
  assert.deepEqual(JSON.parse(c.requests[0].body), payload);
  assert.ok(c.requests[3].url.endsWith('/report/versions/3/citations'));
  for (const request of c.requests) {
    assert.equal(request.headers.get('Authorization'), 'Bearer test-token');
    assert.equal(request.signal, controller.signal);
    assert.equal(request.cache, 'no-store');
  }
});
