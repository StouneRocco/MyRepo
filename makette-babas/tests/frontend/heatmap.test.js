import test from 'node:test';
import assert from 'node:assert/strict';
import {temperatureColor,temperatureGradient,timeLabel,nextMinute,dailySummary,floorDailySeries} from '../../frontend/src/heatmap.js';
test('original projector color scale and white without measurements',()=>{
 assert.equal(temperatureColor(21),'rgb(34,197,94)');
 assert.equal(temperatureColor(null),'#ffffff');
 assert.equal(temperatureColor(NaN),'#ffffff');
 assert.equal(temperatureColor(-5),temperatureColor(12));
 assert.equal(temperatureColor(40),temperatureColor(30));
});
test('Axel playback wraps at the end of the day, 15 minutes per step',()=>{
 assert.equal(nextMinute(1425),0);assert.equal(nextMinute(1435),0);assert.equal(nextMinute(0),15);
 assert.equal(timeLabel(1435),'23:55');
});
test('statistics preserve actual zero and exclude missing readings',()=>{
 assert.deepEqual(dailySummary([0,null,20]),{count:2,min:0,max:20,mean:10});
 assert.equal(dailySummary([null]).mean,null);
});
test('floor curve computes each instant across available plan rooms and preserves zero',()=>{
 const series={a:[0,20,null,NaN],b:[20,null,null,30],unmapped:[100,100,100,100]};
 const result=floorDailySeries(series,[{id:'a'},{id:'b'}],{b:[true,false,false,false]});
 assert.deepEqual(result.values.slice(0,4),[10,20,null,30]);
 assert.deepEqual(result.counts.slice(0,4),[2,1,0,1]);
 assert.deepEqual(result.estimated.slice(0,4),[true,false,false,false]);
 assert.equal(result.values.length,288);
 assert.equal(floorDailySeries(null,[]).values.every(value=>value===null),true);
});

test('site colors match the samples shared with the projector',async()=>{
 const {readFile}=await import('node:fs/promises');
 const {samples}=JSON.parse(await readFile(new URL('../fixtures/temperature-colors.json',import.meta.url),'utf8'));
 for(const {temperature,rgb} of samples)assert.equal(temperatureColor(temperature),`rgb(${rgb.join(',')})`,`${temperature} °C`);
});
test('legend gradient places each shared stop at its temperature',()=>{
 assert.match(temperatureGradient,/^linear-gradient\(90deg,/);
 assert.ok(temperatureGradient.includes('rgb(37,99,235) 0%'));
 assert.ok(temperatureGradient.includes('rgb(34,197,94) 50%'));
 assert.ok(temperatureGradient.includes('rgb(239,68,68) 100%'));
});
test('infinite values are missing readings and labels cover the whole day',()=>{
 assert.equal(temperatureColor(Infinity),'#ffffff');
 assert.equal(temperatureColor(undefined),'#ffffff');
 assert.equal(timeLabel(0),'00:00');assert.equal(timeLabel(65),'01:05');
 assert.equal(nextMinute(1430,5),1435);assert.equal(nextMinute(1435,5),0);
 assert.deepEqual(dailySummary([NaN,Infinity,null]),{count:0,min:null,max:null,mean:null});
});
