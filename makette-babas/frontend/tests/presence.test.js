import test from 'node:test';
import assert from 'node:assert/strict';
import {badgeageRooms,badgeageSelection,nextPresenceHour,presenceSummary,presenceHourLabel,presenceColor,PRESENCE_MAXIMUM} from '../src/presence.js';

test('presence scale stays fixed and zero or missing values have no fill',()=>{
  assert.equal(PRESENCE_MAXIMUM,15);
  for(const value of [0,null,undefined,NaN,-1])assert.equal(presenceColor(value),'none');
  assert.equal(presenceColor(1),'rgb(37,99,235)');
  assert.equal(presenceColor(8),'rgb(34,197,94)');
  assert.equal(presenceColor(15),'rgb(239,68,68)');
  assert.equal(presenceColor(100),presenceColor(15));
  assert.notEqual(presenceColor(10),presenceColor(15));
});

const plan={rooms:[{id:'a',code:'03-A',name:'Salle A'},{id:'b',code:'03-B',name:'Salle B'}]};
const hours=Array(24).fill(0);hours[9]=3;hours[12]=2;
const frame={rooms:{'03-A':{total:5,hours}},hourTotals:hours,total:5};

test('presence keeps Axel room ids and switches from daily to hourly counts',()=>{
  const daily=badgeageRooms(plan,frame);
  assert.equal(daily[0].id,'a');assert.equal(daily[0].count,5);assert.equal(daily[1].count,0);
  assert.equal(badgeageRooms(plan,frame,'9')[0].count,3);
  assert.equal(badgeageRooms(plan,frame,'0')[0].count,0);
});

test('selection changes the hourly chart while floor total stays consistent',()=>{
  const rooms=badgeageRooms(plan,frame,'9');
  const selected=badgeageSelection(rooms,frame,'a','9');
  assert.equal(selected.selectedRoom.name,'Salle A');assert.equal(selected.total,3);
  assert.deepEqual(selected.distribution,hours);
  const zero=badgeageSelection(rooms,frame,'b','9');
  assert.deepEqual(zero.distribution,Array(24).fill(0));
});

test('loading and zero counts never invent a badgeage',()=>{
  assert.deepEqual(badgeageRooms(plan,null),[]);
  assert.equal(badgeageSelection([],null,null).maximum,0);
  assert.equal(badgeageSelection(badgeageRooms(plan,frame,'0'),frame,null,'0').total,0);
});

test('hourly timeline wraps at midnight and summaries include the 24 hours',()=>{
  assert.equal(nextPresenceHour(23),0);
  assert.equal(nextPresenceHour(9),10);
  assert.equal(presenceHourLabel(9),'09:00');
  assert.deepEqual(presenceSummary(hours),{total:5,mean:5/24,peak:3});
  assert.deepEqual(presenceSummary(Array(24).fill(0)),{total:0,mean:0,peak:0});
});
