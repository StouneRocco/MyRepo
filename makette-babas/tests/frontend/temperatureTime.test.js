import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {dayTimestamp,parisDay} from '../../frontend/src/temperatureTime.js';

test('Paris midnight is the day boundary, in winter and in summer',()=>{
  assert.equal(parisDay(Date.UTC(2025,11,31,22,59)),'2025-12-31');
  assert.equal(parisDay(Date.UTC(2025,11,31,23,0)),'2026-01-01');
  assert.equal(parisDay(Date.UTC(2026,5,29,22,0)),'2026-06-30');
  assert.equal(dayTimestamp('2026-01-01',0),Date.UTC(2025,11,31,23));
  assert.equal(dayTimestamp('2026-06-30',840),Date.UTC(2026,5,30,12));
  assert.equal(dayTimestamp('2026-06-30',1435),Date.UTC(2026,5,30,21,55));
});

test('daylight saving days use the right offset on each side of the change',()=>{
  assert.equal(dayTimestamp('2026-03-29',60),Date.UTC(2026,2,29,0));
  assert.equal(dayTimestamp('2026-03-29',180),Date.UTC(2026,2,29,1));
  assert.equal(dayTimestamp('2026-10-25',60),Date.UTC(2026,9,24,23));
  assert.equal(dayTimestamp('2026-10-25',240),Date.UTC(2026,9,25,3));
});

test('every five-minute slot of a day stays on that Paris day',()=>{
  for(const day of ['2026-01-01','2026-03-29','2026-06-30','2026-10-25']){
    for(let minute=0;minute<1440;minute+=5){
      if(day==='2026-03-29'&&minute>=120&&minute<180)continue; // heure inexistante
      assert.equal(parisDay(dayTimestamp(day,minute)),day,`${day} ${minute}`);
    }
  }
});

test('conversion does not depend on the device time zone',()=>{
  const module=new URL('../../frontend/src/temperatureTime.js',import.meta.url).href;
  const code=`import {dayTimestamp} from ${JSON.stringify(module)};process.stdout.write(String(dayTimestamp('2026-06-30',840)));`;
  for(const TZ of ['America/New_York','Pacific/Auckland','UTC']){
    const output=execFileSync(process.execPath,['--input-type=module','-e',code],{env:{...process.env,TZ},encoding:'utf8'});
    assert.equal(Number(output.trim()),Date.UTC(2026,5,30,12),TZ);
  }
});
