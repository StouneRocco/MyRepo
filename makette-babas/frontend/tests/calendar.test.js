import test from 'node:test';
import assert from 'node:assert/strict';
import {availableMonths,dayInMonth,monthLabel} from '../src/calendar.js';
test('all six imported months remain directly selectable',()=>{
  const days=['2026-01-01','2026-02-01','2026-03-01','2026-04-01','2026-05-01','2026-06-01','2026-06-30'];
  assert.deepEqual(availableMonths(days),['2026-01','2026-02','2026-03','2026-04','2026-05','2026-06']);
  assert.equal(dayInMonth(days,'2026-06','2026-01-30'),'2026-06-30');
  assert.equal(monthLabel('2026-06'),'juin 2026');
});
test('a shorter month uses an existing date and never invents readings',()=>{
  assert.equal(dayInMonth(['2026-02-01','2026-02-28'],'2026-02','2026-01-31'),'2026-02-01');
  assert.equal(dayInMonth(['2026-01-01'],'2026-06','2026-01-01'),null);
});
