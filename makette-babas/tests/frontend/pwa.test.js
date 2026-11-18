import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const frontend=new URL('../../frontend/',import.meta.url);
const read=path=>readFile(new URL(path,frontend),'utf8');

function loadServiceWorker(source,fetch){
  const handlers={},calls={skipWaiting:0,claim:0};
  const self={addEventListener:(type,handler)=>{handlers[type]=handler;},skipWaiting:()=>{calls.skipWaiting++;},
    clients:{claim:()=>{calls.claim++;return Promise.resolve();}}};
  vm.runInNewContext(source,{self,fetch,Response});
  return {handlers,calls};
}
function fetchEvent(mode){
  const event={request:{mode,url:'https://10.0.0.1:5000/'},responded:null,respondWith(value){this.responded=value;}};
  return event;
}

test('installed app opens without browser bar and with existing icons',async()=>{
  const manifest=JSON.parse(await read('public/manifest.webmanifest'));
  assert.equal(manifest.display,'standalone');
  assert.equal(manifest.start_url,'/');
  assert.equal(manifest.lang,'fr');
  for(const icon of manifest.icons){
    const png=await readFile(new URL('public'+icon.src,frontend));
    assert.equal(png.toString('ascii',1,4),'PNG',icon.src);
    const [width,height]=icon.sizes.split('x').map(Number);
    assert.deepEqual([png.readUInt32BE(16),png.readUInt32BE(20)],[width,height],icon.src);
  }
  const html=await read('index.html');
  assert.match(html,/<html lang="fr">/);
  assert.match(html,/rel="manifest" href="\/manifest.webmanifest"/);
});

test('service worker activates immediately',async()=>{
  const {handlers,calls}=loadServiceWorker(await read('public/sw.js'),()=>{});
  handlers.install();
  let waited=null;handlers.activate({waitUntil:promise=>{waited=promise;}});
  await waited;
  assert.deepEqual(calls,{skipWaiting:1,claim:1});
});

test('service worker only intercepts page navigations, never from cache',async()=>{
  const requests=[];
  const {handlers}=loadServiceWorker(await read('public/sw.js'),(request,options)=>{requests.push(options);return Promise.resolve(new Response('ok'));});
  const api=fetchEvent('cors');handlers.fetch(api);
  assert.equal(api.responded,null);
  const page=fetchEvent('navigate');handlers.fetch(page);
  assert.equal(await (await page.responded).text(),'ok');
  assert.deepEqual(requests.map(options=>options.cache),['no-store']);
});

test('offline navigation shows a French retry page',async()=>{
  const {handlers}=loadServiceWorker(await read('public/sw.js'),()=>Promise.reject(new TypeError('offline')));
  const page=fetchEvent('navigate');handlers.fetch(page);
  const response=await page.responded;
  assert.equal(response.status,503);
  assert.match(response.headers.get('content-type'),/text\/html/);
  const body=await response.text();
  assert.match(body,/Serveur indisponible/);
  assert.match(body,/Réessayer/);
});
