import test from 'node:test';
import assert from 'node:assert/strict';
import {api} from '../../frontend/src/api.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8'}});
function stubFetch(t,implementation){
  const calls=[];
  const original=globalThis.fetch;
  globalThis.fetch=(url,options)=>{calls.push({url,options});return implementation(url,options);};
  t.after(()=>{globalThis.fetch=original;});
  return calls;
}

test('GET carries the session token and no body',async t=>{
  const calls=stubFetch(t,()=>Promise.resolve(json([{floor:3}])));
  assert.deepEqual(await api('plans','token-123'),[{floor:3}]);
  assert.equal(calls[0].url,'/api/plans');
  assert.equal(calls[0].options.method,'GET');
  assert.equal(calls[0].options.headers.Authorization,'Bearer token-123');
  assert.equal(calls[0].options.body,undefined);
});

test('POST serializes the body and omits Authorization without session',async t=>{
  const calls=stubFetch(t,()=>Promise.resolve(json({token:'x'},201)));
  await api('login',null,{username:'alice',password:'secret'});
  assert.equal(calls[0].options.method,'POST');
  assert.equal(calls[0].options.headers['Content-Type'],'application/json');
  assert.equal('Authorization' in calls[0].options.headers,false);
  assert.deepEqual(JSON.parse(calls[0].options.body),{username:'alice',password:'secret'});
  await api('projection-retry','t',{});
  assert.equal(calls[1].options.method,'POST');
  assert.equal(calls[1].options.body,'{}');
});

test('server errors keep their message and HTTP status',async t=>{
  stubFetch(t,url=>Promise.resolve(url.endsWith('plans')?json({error:'Session expirée'},401):json({},500)));
  await assert.rejects(api('plans','t'),error=>error.message==='Session expirée'&&error.status===401);
  await assert.rejects(api('other','t'),error=>error.message==='Erreur serveur'&&error.status===500);
});

test('an HTML answer means an outdated backend, not a JSON crash',async t=>{
  stubFetch(t,()=>Promise.resolve(new Response('<!doctype html>',{headers:{'content-type':'text/html'}})));
  await assert.rejects(api('badgeages/days/3','t'),/ne reconnaît pas \/api\/badgeages\/days\/3/);
});

test('network failures are reported unchanged',async t=>{
  stubFetch(t,()=>Promise.reject(new TypeError('Failed to fetch')));
  await assert.rejects(api('plans','t'),/Failed to fetch/);
});

test('a request is abandoned after ten seconds with a clear message',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  stubFetch(t,(url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')))));
  const pending=api('plans','t');
  t.mock.timers.tick(9999);
  let settled=false;pending.catch(()=>{}).finally(()=>{settled=true;});
  await new Promise(resolve=>setImmediate(resolve));assert.equal(settled,false);
  t.mock.timers.tick(1);
  await assert.rejects(pending,/trop de temps/);
});
