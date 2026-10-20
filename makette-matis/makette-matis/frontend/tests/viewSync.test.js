import test from 'node:test';
import assert from 'node:assert/strict';
import {createViewSync} from '../src/viewSync.js';
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
test('a stale poll cannot undo a newer edit',async()=>{
  const poll=deferred(), edit=deferred(), seen=[];
  const sync=createViewSync(body=>body?edit.promise:poll.promise,data=>seen.push(data),()=>{});
  const refreshing=sync.refresh();const saving=sync.change({day:'2026-06-30'});
  edit.resolve({revision:2,day:'2026-06-30'});await saving;
  poll.resolve({revision:1,day:'2026-01-01'});await refreshing;
  assert.deepEqual(seen,[{revision:2,day:'2026-06-30'}]);
});
test('rapid field edits stay ordered and only the final shared response is applied',async()=>{
  const first=deferred(), calls=[], seen=[];
  const sync=createViewSync(body=>{calls.push(body);return calls.length===1?first.promise:Promise.resolve({revision:3,day:'2026-06-30',minute:840});},data=>seen.push(data),()=>{});
  const a=sync.change({day:'2026-06-30'});const b=sync.change({minute:840});
  first.resolve({revision:2,day:'2026-06-30',minute:0});await a;await b;
  assert.deepEqual(calls,[{day:'2026-06-30'},{minute:840}]);
  assert.equal(seen.length,1);assert.equal(seen[0].minute,840);
});
