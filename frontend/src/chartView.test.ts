import {describe,it,expect} from 'vitest';
import {candleWindow,zoomBars,priceZoom} from './chartView';
describe('observed-candle chart navigation',()=>{
 it('bounds history offsets and never creates candles',()=>{
  expect(candleWindow(100,64,0)).toEqual({start:36,end:100,size:64,offset:0});
  expect(candleWindow(100,64,999)).toEqual({start:0,end:64,size:64,offset:36});
  expect(candleWindow(100,64,-2).end).toBe(100);
 });
 it('clamps zoom to available observations',()=>{
  expect(zoomBars(64,.01,100)).toBe(12);
  expect(zoomBars(64,100,100)).toBe(100);
  expect(zoomBars(64,.1,3)).toBe(3);
  expect(candleWindow(3,64,20)).toEqual({start:0,end:3,size:3,offset:0});
 });
 it('keeps a positive bounded price scale',()=>{
  expect(priceZoom(.01)).toBe(.2);
  expect(priceZoom(100)).toBe(5);
 });
});

import {axisDragScale} from './chartView';
describe('price-axis hold and drag',()=>{
 it('compresses down, stretches up and preserves scale at zero movement',()=>{
  expect(axisDragScale(1,100,500)).toBeGreaterThan(1);
  expect(axisDragScale(1,-100,500)).toBeLessThan(1);
  expect(axisDragScale(1.5,0,500)).toBe(1.5);
 });
 it('uses the gesture start scale and clamps extreme drags',()=>{
  expect(axisDragScale(1,10000,500)).toBe(5);
  expect(axisDragScale(1,-10000,500)).toBe(.2);
  expect(axisDragScale(2,50,500)).toBeCloseTo(2*Math.exp(.2));
 });
});
