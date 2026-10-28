"""Candle evidence describes behavior, never trader identity or actual resting orders."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from .engine import Candle, aggregate
from .market_analysis import confirmed_swings, swing_sweeps, fair_value_gaps
from .price_action import structure

@dataclass(frozen=True)
class PressureRules:
    minimum_bars: int = 30
    lookback_bars: int = 12
    baseline_bars: int = 20
    displacement_multiple: float = 1.5
    displacement_body_fraction: float = 0.65
    rejection_wick_fraction: float = 0.5
    repeated_rejections: int = 2
    minimum_agreement: int = 2
    compression_fraction: float = 0.7

RULES = PressureRules()

def pressure_frame(bars: list[Candle], timeframe: int, now: int) -> dict:
    """Only completed bars and pivots already known at each rejection can contribute."""
    candles = aggregate(bars, timeframe*60, now)
    result = dict(timeframe=f'M{timeframe}' if timeframe!=60 else 'H1', status='unavailable',
        reading='Unavailable', evidence=[], buy_count=0, sell_count=0, range_note=None,
        last_closed_at=candles[-1].time+timeframe*60 if candles else None)
    if len(candles)<RULES.minimum_bars:
        result['reason']=f'Need {RULES.minimum_bars} completed candles; {len(candles)} available.'
        return result
    if now-candles[-1].time-timeframe*60>timeframe*60:
        result['reason']='Completed candle context is stale.'
        return result
    last=candles[-1]
    baseline=median(c.high-c.low for c in candles[-RULES.baseline_bars-1:-1])
    span=last.high-last.low
    evidence=[]
    state=structure(candles)[-1]
    if state['bias']:
        evidence.append(dict(kind='structure',side=state['bias'],detail=f"Confirmed structure points {state['bias']}; candle-based context."))
    if baseline>0 and span>=baseline*RULES.displacement_multiple and abs(last.close-last.open)>=span*RULES.displacement_body_fraction:
        evidence.append(dict(kind='displacement',side='BUY' if last.close>last.open else 'SELL',detail='Latest completed candle expands beyond the prior median range with a large body.'))
    swings=confirmed_swings(candles)
    recent=candles[-RULES.lookback_bars:]
    sweeps=swing_sweeps(candles,swings)
    for side,label in [('BUY','bullish'),('SELL','bearish')]:
        matching=[s for s in sweeps if s['side']==label and s['time']>=recent[0].time]
        if matching:evidence.append(dict(kind='sweep',side=side,detail=f'{len(matching)} recent wick sweep(s) of previously confirmed swings; not observed stop orders.'))
        rejects=[]
        kind='low' if side=='BUY' else 'high'
        for b in recent:
            known=[s for s in swings if s['kind']==kind and s['confirmed_at']<=b.time]
            if not known or b.high<=b.low:continue
            level=known[-1]['price']
            wick=min(b.open,b.close)-b.low if side=='BUY' else b.high-max(b.open,b.close)
            crossed=b.low<=level<b.close if side=='BUY' else b.high>=level>b.close
            if crossed and wick/(b.high-b.low)>=RULES.rejection_wick_fraction:
                rejects.append((b.time,level))
        # Repetition must be around the same known pivot, not unrelated resistance levels.
        by_level={level:sum(v==level for _,v in rejects) for _,level in rejects}
        count=max(by_level.values(),default=0)
        if count>=RULES.repeated_rejections:evidence.append(dict(kind='rejection',side=side,detail=f'{count} wick rejections around the same confirmed swing level.'))
        gaps=[g for g in fair_value_gaps(candles) if g['side']==label and g['time']>=recent[0].time]
        if gaps:evidence.append(dict(kind='imbalance',side=side,detail=f'{len(gaps)} recent unfilled three-candle gap(s); a price pattern, not an order-book imbalance.'))
    buy=sum(e['side']=='BUY' for e in evidence);sell=sum(e['side']=='SELL' for e in evidence)
    reading='Mixed / inconclusive'
    if buy>=RULES.minimum_agreement and sell==0:reading='Buying-pressure evidence'
    if sell>=RULES.minimum_agreement and buy==0:reading='Selling-pressure evidence'
    earlier=candles[-2*RULES.lookback_bars:-RULES.lookback_bars]
    recent_range=max(c.high for c in recent)-min(c.low for c in recent)
    prior_range=max(c.high for c in earlier)-min(c.low for c in earlier)
    range_note=('Range compression observed. Accumulation versus distribution cannot be determined from OHLC alone.'
        if prior_range>0 and recent_range<=prior_range*RULES.compression_fraction else None)
    result.update(status='available',reason='Unweighted candle-evidence counts, not confidence or a trade instruction.',
        reading=reading,evidence=evidence,buy_count=buy,sell_count=sell,range_note=range_note)
    return result

def pressure_snapshot(bars: list[Candle], now: int, fresh: bool) -> dict:
    frames=[pressure_frame(bars,tf,now) for tf in (15,30,60)]
    if not fresh:
        for frame in frames:
            frame.update(status='unavailable',reading='Unavailable',reason='Market feed is disconnected or stale.',evidence=[],buy_count=0,sell_count=0,range_note=None)
    return dict(method='OHLC pressure proxy v1; no AI prediction',frames=frames,
        institutional_identity='unavailable',pending_orders='unavailable',tick_volume='unavailable',order_book='unavailable',
        limitation='Candles cannot prove institutional activity, accumulation, or resting orders. Evidence counts are not probabilities. Analysis only; does not change entry rules.')
