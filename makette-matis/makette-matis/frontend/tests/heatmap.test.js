import test from 'node:test';
import assert from 'node:assert/strict';
import {temperatureColor,timeLabel,nextMinute,dailySummary} from '../src/heatmap.js';
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
