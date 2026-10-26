const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function compile(file) {
  return ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
}

const labels = { exports: {} };
vm.runInNewContext(compile('../src/lib/monitoring.ts'), labels);

test('stage names handle live and resumed workflow conventions without inventing a stage', () => {
  const m = labels.exports;
  assert.equal(m.stageKey('POST_PROCESSOR'), 'POST_PROCESSOR');
  assert.equal(m.stageKey('Supervisor'), 'SUPERVISOR');
  assert.equal(m.stageKey('Waiting for dataset'), 'METHODOLOGIST');
  assert.equal(m.stageKey('BUDGET_LIMIT'), '');
  assert.equal(m.stageKey(null), '');
  assert.equal(m.stagesFor('REVIEW').some(stage => stage.key === 'EXPERIMENT_RUNNER'), false);
  assert.equal(m.stagesFor('EMPIRICAL_COMPUTATIONAL').some(stage => stage.key === 'EXPERIMENT_RUNNER'), true);
  assert.equal(m.stagesFor('EMPIRICAL_HUMAN').some(stage => stage.key === 'EXPERIMENT_RUNNER'), false);
  assert.equal(m.outputLabel('verdict', 'NO_IMPROVEMENT'), 'Kết luận: Không cải thiện so với baseline');
});

function mount(load, hidden = false) {
  const state = [], timers = new Map();
  let stateIndex = 0, timerId = 0, cleanup;
  const doc = { visibilityState: hidden ? 'hidden' : 'visible' };
  const context = { exports: {}, AbortController, Date, Error, document: doc,
    setTimeout: (fn, delay) => { const id = ++timerId; timers.set(id, { fn, delay }); return id; },
    clearTimeout: id => timers.delete(id),
    require: name => {
      assert.equal(name, 'react');
      return {
        useState: initial => {
          const index = stateIndex++;
          state[index] = initial;
          return [initial, value => { state[index] = typeof value === 'function' ? value(state[index]) : value; }];
        },
        useCallback: fn => fn,
        useEffect: effect => { cleanup = effect(); },
      };
    },
  };
  vm.runInNewContext(compile('../src/lib/use-monitor-poll.ts'), context);
  context.exports.useMonitorPoll(load, 5000);
  const tick = async () => { await Promise.resolve(); await Promise.resolve(); };
  return { state, timers, doc, unmount: () => cleanup(), tick,
    runNext: async delay => {
      const entry = [...timers].find(([, timer]) => timer.delay === delay);
      assert.ok(entry, `expected a ${delay}ms timer`);
      timers.delete(entry[0]);
      entry[1].fn();
      await tick();
    },
  };
}

test('polling does not overlap a pending request and ignores its result after leaving the page', async () => {
  let resolve, signal, requests = 0;
  const hook = mount(value => { signal = value; requests++; return new Promise(done => { resolve = done; }); });
  assert.equal(requests, 1);
  assert.equal([...hook.timers.values()].some(timer => timer.delay === 5000), false);
  hook.unmount();
  assert.equal(signal.aborted, true);
  resolve({ task_id: 'old-paper' });
  await hook.tick();
  assert.equal(hook.state[0], null);
  assert.equal(hook.timers.size, 0);
});

test('a temporary network failure keeps last successful data and schedules a retry', async () => {
  let calls = 0;
  const snapshot = { task_id: 'paper', status: 'RUNNING' };
  const hook = mount(async () => { if (++calls === 1) return snapshot; throw new Error('offline'); });
  await hook.tick();
  assert.equal(hook.state[0], snapshot);
  await hook.runNext(5000);
  assert.equal(hook.state[0], snapshot);
  assert.match(hook.state[1], /Kiểm tra kết nối/);
  assert.ok([...hook.timers.values()].some(timer => timer.delay === 5000));
  hook.unmount();
});

test('hidden tabs defer polling and begin fetching when visible again', async () => {
  let requests = 0;
  const hook = mount(async () => { requests++; return {}; }, true);
  assert.equal(requests, 0);
  await hook.runNext(5000);
  assert.equal(requests, 0);
  hook.doc.visibilityState = 'visible';
  await hook.runNext(5000);
  assert.equal(requests, 1);
  hook.unmount();
});

test('deleted or no-longer-authorized papers clear cached data and stop automatic polling', async () => {
  let calls = 0;
  const hook = mount(async () => {
    if (++calls === 1) return { task_id: 'deleted-paper' };
    throw Object.assign(new Error('Research task not found'), { status: 404 });
  });
  await hook.tick();
  assert.ok(hook.state[0]);
  await hook.runNext(5000);
  assert.equal(hook.state[0], null);
  assert.equal(hook.state[3], null);
  assert.equal(hook.timers.size, 0);
  hook.unmount();
});
