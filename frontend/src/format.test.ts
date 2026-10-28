import {describe,it,expect} from 'vitest';
import {money,date,csvCell} from './format';
describe('display and export boundaries',()=>{
 it('preserves valid zero and two decimal places',()=>expect(money(0)).toBe('0.00'));
 it('uses UTC independently of client timezone',()=>expect(date(0)).toBe('01 Jan, 00:00 UTC'));
 it('escapes quoted fields for journal exports',()=>expect(csvCell('a,"b"')).toBe('"a,""b"""'));
});

import {profileSignals,strategyLabel,CURRENT_STRATEGY} from './format';
import type {Signal} from './types';
describe('strategy performance isolation',()=>{
 it('keeps legacy breakout and the other profile out of current metrics',()=>{
  const signals=[{id:'new',profile:'scalping',strategy:CURRENT_STRATEGY},{id:'old',profile:'scalping',strategy:'scalping-breakout-ema-atr-v2'},{id:'day',profile:'intraday',strategy:CURRENT_STRATEGY},{id:'first'}] as Signal[];
  expect(profileSignals(signals,'scalping').map(s=>s.id)).toEqual(['new']);
  expect(strategyLabel(signals[1])).toBe('Legacy breakout');
  expect(strategyLabel(signals[0])).toBe('MTF confirmation · 2R target');
 });
});

import {resultPips} from './format';
describe('pip results',()=>{
 it('uses observed prices for both directions',()=>{
  expect(resultPips({status:'TP3',side:'BUY',fill_price:4200,exit_price:4204} as Signal)).toBe(40);
  expect(resultPips({status:'STOPPED',side:'SELL',fill_price:4200,exit_price:4203} as Signal)).toBe(-30);
 });
 it('does not infer pips from R or an unfilled signal',()=>{
  expect(resultPips({status:'TP3',result_r:2} as Signal)).toBeNull();
  expect(resultPips({status:'PENDING',fill_price:4200,exit_price:4204} as Signal)).toBeNull();
 });
});
