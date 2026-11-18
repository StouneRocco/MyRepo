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

test('slider movements merge while an update is in flight',async()=>{
  const first=deferred(),calls=[],seen=[];
  const sync=createViewSync(body=>{calls.push(body);return calls.length===1?first.promise:Promise.resolve({revision:2,...body});},data=>seen.push(data),()=>{});
  const promises=[sync.change({minute:5})];
  for(let minute=10;minute<=250;minute+=5)promises.push(sync.change({minute}));
  promises.push(sync.change({playing:false}));
  first.resolve({revision:1,minute:5});await Promise.all(promises);
  assert.deepEqual(calls,[{minute:5},{minute:250,playing:false}]);
  assert.equal(seen.length,1);assert.equal(seen[0].minute,250);
});

test('polling never overlaps and a failed save allows subsequent edits',async()=>{
  const poll=deferred();let reads=0,errors=0;
  const sync=createViewSync(body=>{if(!body){reads++;return poll.promise;}if(body.minute===5)throw Error('offline');return Promise.resolve({revision:2,...body});},()=>{},()=>errors++);
  const a=sync.refresh(),b=sync.refresh();
  await Promise.resolve();assert.equal(reads,1);
  poll.resolve({revision:0});await Promise.all([a,b]);
  await sync.change({minute:5});await sync.change({minute:10});
  assert.equal(errors,1);
});
