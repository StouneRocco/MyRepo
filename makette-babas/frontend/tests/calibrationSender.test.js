import test from 'node:test';
import assert from 'node:assert/strict';
import { createCalibrationSender } from '../src/calibrationSender.js';

test('slow receiver gets the latest movement without concurrent requests or stale saves', async () => {
  const calls = [], completions = [];
  const send = createCalibrationSender(value => {
    calls.push(value);
    return new Promise(resolve => completions.push(resolve));
  });
  const first = send({x:1, persist:false});
  const skipped = send({x:2, persist:false});
  const last = send({x:3, persist:false});
  assert.deepEqual(calls, [{x:1, persist:false}]);
  completions[0]('first'); await first;
  assert.deepEqual(calls, [{x:1, persist:false}, {x:3, persist:false}]);
  const save = send({x:3, persist:true});
  completions[1]('latest');
  assert.equal(await skipped, 'latest'); await last;
  assert.equal(calls.at(-1).persist, true);
  completions[2]('saved'); assert.equal(await save, 'saved');
});

test('receiver failure does not block the next adjustment', async () => {
  let rejectFirst;
  const send = createCalibrationSender(value => value === 1
    ? new Promise((resolve,reject) => { rejectFirst = reject; }) : Promise.resolve(value));
  const failed = send(1);
  const verified = assert.rejects(failed, /unavailable/);
  const next = send(2);
  rejectFirst(new Error('unavailable'));
  await verified;
  assert.equal(await next, 2);
});
