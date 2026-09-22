const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function setup() {
  const state = { store: new Map(), reads: [], uploads: 0, fail: false, restricted: false, registered: false };
  const modules = {
    'expo-background-task': { BackgroundTaskResult: { Success: 1, Failed: 2 }, BackgroundTaskStatus: { Restricted: 1 }, getStatusAsync: async () => state.restricted ? 1 : 2, registerTaskAsync: async () => { state.registered = true; }, unregisterTaskAsync: async () => { state.registered = false; } },
    'expo-task-manager': { defineTask: (_, fn) => state.task = fn, isTaskRegisteredAsync: async () => state.registered },
    'expo-secure-store': { getItemAsync: async k => state.store.get(k) ?? null, setItemAsync: async (k,v) => state.store.set(k,v) },
    './health': { readDailyHealth: async (_, authorize) => { state.reads.push(authorize); return [{ date: '2026-09-22' }]; } },
    './sync': { loadSettings: async () => ({ authorized: true, accessKey: 'test' }), markAuthorized: async () => {}, sendSummaries: async () => { state.uploads++; if (state.fail) throw new Error('offline'); } },
  };
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync('src/automaticSync.ts','utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(code, { exports, require: name => modules[name], Date, Promise });
  return { state, api: exports };
}
test('background is opt-in and never requests authorization', async () => {
  const { state, api } = setup();
  assert.equal(await state.task(), 1);
  assert.equal(state.reads.length, 0);
  await api.setAutomaticSync(true);
  assert.equal(await state.task(), 1);
  assert.deepEqual(state.reads, [false]);
  assert.equal((await api.loadHistory()).latestDate, '2026-09-22');
  await api.setAutomaticSync(false);
  assert.equal(state.registered, false);
});
test('failed upload preserves last successful sync', async () => {
  const { state, api } = setup();
  await api.setAutomaticSync(true);
  await state.task();
  const before = JSON.stringify(await api.loadHistory());
  state.fail = true;
  assert.equal(await state.task(), 2);
  assert.equal(JSON.stringify(await api.loadHistory()), before);
});
test('overlapping triggers share one upload', async () => {
  const { state, api } = setup();
  await Promise.all([api.performSync({}, true, 'Manual'), api.performSync({}, false, 'Background')]);
  assert.equal(state.uploads, 1);
});
test('restricted scheduling does not enable automatic syncing', async () => {
  const { state, api } = setup();
  state.restricted = true;
  await assert.rejects(api.setAutomaticSync(true));
  assert.equal(await api.automaticEnabled(), false);
});
