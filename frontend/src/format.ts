import type {Signal} from './types';
export const money = (n:number) => n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
export const date = (n:number) => new Date(n*1000).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'UTC'})+' UTC';
export function csvCell(value:unknown){return '"'+String(value??'').replaceAll('"','""')+'"'}

export const CURRENT_STRATEGY='aurum-mtf-confirmation-v5';
export function profileSignals(signals:Signal[],profile:string){return signals.filter(s=>s.profile===profile&&s.strategy===CURRENT_STRATEGY)}
export function strategyLabel(s:Signal){return s.strategy===CURRENT_STRATEGY?'MTF confirmation · 2R target':s.strategy==='supply-demand-rr-v4'?'Legacy zones · 1R / 2R / 3R':s.strategy==='supply-demand-structure-v3'?'Legacy structure targets':s.strategy==='supply-demand-fixed-pips-v2'?'Legacy fixed pips':s.strategy==='structure-supply-demand-v1'?'Legacy SMC · structural TP':'Legacy breakout'}

export function resultPips(signal:Signal):number|null {
 if(!['STOPPED','TP3'].includes(signal.status)||signal.fill_price==null||signal.exit_price==null)return null;
 return Math.round((signal.exit_price-signal.fill_price)*(signal.side==='BUY'?1:-1)/0.1*100)/100;
}
