"""Mechanical interpretation of video _LLXjCdLSPE; no profitability claim.

All inputs are completed candles. Pivots require two subsequent completed bars.
Thresholds here are explicit implementation choices, not parameters from the video.
"""
from statistics import median

STRATEGY = 'structure-supply-demand-v1'


def structure(candles):
    """A continuation break validates a pullback; internal pivots do not flip bias."""
    highs, lows = [], []
    bias, protected, protected_index, event = None, None, None, None
    extreme, extreme_index = None, None
    states = []
    for i, bar in enumerate(candles):
        pivot = i - 2
        if pivot >= 2:
            window = candles[pivot-2:pivot+3]
            if all(candles[pivot].high > b.high for n,b in enumerate(window) if n != 2):
                highs.append((pivot, candles[pivot].high))
            if all(candles[pivot].low < b.low for n,b in enumerate(window) if n != 2):
                lows.append((pivot, candles[pivot].low))
        if bias == 'BUY' and bar.close < protected:
            protected_index = max(range(protected_index,i+1), key=lambda n:candles[n].high)
            protected = candles[protected_index].high
            bias, event, extreme, extreme_index = 'SELL', 'CHoCH', bar.low, i
        elif bias == 'SELL' and bar.close > protected:
            protected_index = min(range(protected_index,i+1), key=lambda n:candles[n].low)
            protected = candles[protected_index].low
            bias, event, extreme, extreme_index = 'BUY', 'CHoCH', bar.high, i
        elif bias == 'BUY':
            pullbacks = [p for p in lows if p[0] > extreme_index]
            validated = False
            if bar.close > extreme and pullbacks:
                index, level = min(pullbacks, key=lambda p:p[1])
                if level > protected:
                    protected_index, protected, event = index, level, 'BOS'
                    validated = True
            if bar.high > extreme:
                if not pullbacks or validated:
                    extreme_index = i
                extreme = bar.high
        elif bias == 'SELL':
            pullbacks = [p for p in highs if p[0] > extreme_index]
            validated = False
            if bar.close < extreme and pullbacks:
                index, level = max(pullbacks, key=lambda p:p[1])
                if level < protected:
                    protected_index, protected, event = index, level, 'BOS'
                    validated = True
            if bar.low < extreme:
                if not pullbacks or validated:
                    extreme_index = i
                extreme = bar.low
        elif highs and bar.close > highs[-1][1]:
            pullbacks = [p for p in lows if p[0] > highs[-1][0]]
            if pullbacks:
                protected_index, protected = min(pullbacks, key=lambda p:p[1])
                bias, event, extreme, extreme_index = 'BUY', 'BOS', bar.high, i
        elif lows and bar.close < lows[-1][1]:
            pullbacks = [p for p in highs if p[0] > lows[-1][0]]
            if pullbacks:
                protected_index, protected = max(pullbacks, key=lambda p:p[1])
                bias, event, extreme, extreme_index = 'SELL', 'BOS', bar.low, i
        states.append(dict(bias=bias, protected=protected, event=event))
    return states


def find_zones(candles, states, require_alignment=True):
    zones = []
    for i in range(14,len(candles)):
        bar, base = candles[i], candles[i-1]
        typical = median(b.high-b.low for b in candles[i-14:i])
        if typical <= 0:
            continue
        consolidation = candles[i-3:i]
        if max(b.high for b in consolidation)-min(b.low for b in consolidation) > 2*typical:
            continue
        if any(abs(b.close-b.open) > .6*typical for b in consolidation):
            continue
        body, span = abs(bar.close-bar.open), bar.high-bar.low
        if body < 1.5*typical or span <= 0 or base.high <= base.low:
            continue
        side = 'BUY' if bar.close > bar.open else 'SELL'
        if require_alignment and states[i]['bias'] != side:
            continue
        if side == 'BUY':
            qualifies = bar.close > max(b.high for b in consolidation) and bar.close >= bar.low+.75*span
        else:
            qualifies = bar.close < min(b.low for b in consolidation) and bar.close <= bar.low+.25*span
        if qualifies:
            zones.append(dict(index=i, low=round(base.low,2), high=round(base.high,2), side=side,
                              time=base.time, confirmed_at=bar.time, typical=typical))
    return zones


def contiguous_tail(candles, seconds):
    for i in range(len(candles)-1,0,-1):
        if candles[i].time-candles[i-1].time != seconds:
            return candles[i:]
    return candles


def evaluate_candles(candles, timeframe, now):
    if len(candles) < 30:
        return None, f'Warming up: at least 30 completed M{timeframe} candles required.'
    # Do not infer structure across a market-session hole.
    candles = contiguous_tail(candles,timeframe*60)
    if len(candles) < 30:
        return None, 'Session gap: waiting for 30 contiguous completed setup candles.'
    states = structure(candles)
    current = states[-1]
    if current['bias'] is None:
        return None, 'Waiting for a confirmed swing break and validated pullback (no EMA filter).'
    last = candles[-1]
    reason = f"{current['bias']} structure: waiting for a fresh {'demand' if current['bias']=='BUY' else 'supply'} zone with at least 2.5:1 reward/risk."
    for zone in reversed(find_zones(candles,states)):
        i, side = zone['index'], zone['side']
        if side != current['bias'] or len(candles)-1-i > 12:
            continue
        # No reuse after a historical touch, including an adverse gap past the zone.
        after = candles[i+1:]
        touched = any(b.low <= zone['high'] for b in after) if side == 'BUY' else any(b.high >= zone['low'] for b in after)
        if touched:
            continue
        if any(s['bias'] != side for s in states[i:]):
            continue
        direction = 1 if side == 'BUY' else -1
        low, high = zone['low'], zone['high']
        if high <= low:
            continue
        buffer = max(.01, round((high-low)*.1,2))
        stop = round(low-buffer if side=='BUY' else high+buffer,2)
        target = round(max(b.high for b in candles[i:]) if side=='BUY' else min(b.low for b in candles[i:]),2)
        worst = high if side=='BUY' else low
        rr = (target-worst)*direction/abs(worst-stop)
        if rr < 2.5:
            reason = f'Fresh zone found, but recent-extreme reward/risk is {rr:.2f}:1 at the least favorable zone entry; minimum 2.5:1.'
            continue
        entry = round((low+high)/2,2)
        distance = (target-entry)*direction
        risk = round(abs(entry-stop),2)
        targets = [round(entry+direction*distance*f,2) for f in (1/3,2/3,1)]
        if not (risk > 0 and all((t-entry)*direction > 0 for t in targets) and len(set(targets))==3):
            continue
        profile = 'scalping' if timeframe==5 else 'intraday'
        return dict(profile=profile,strategy=STRATEGY,timeframe=f'M{timeframe}',bar_time=last.time,
            zone_id=f'{STRATEGY}:M{timeframe}:{zone["time"]}:{side}',
            zone_type='demand' if side=='BUY' else 'supply',zone_time=zone['time'],zone_confirmed_at=zone['confirmed_at'],
            protected_level=current['protected'],structure_event=current['event'],minimum_rr=2.5,planned_rr=round(rr,3),
            created_at=now,side=side,entry=entry,entry_low=low,entry_high=high,stop=stop,targets=targets,risk=risk,
            status='PENDING',filled_at=None,closed_at=None,fill_price=None,result_r=None,targets_hit=0,
            expires_at=now+timeframe*60*3,
            explanation=[f'M{timeframe} {side} structure; validated protective level {current["protected"]:.2f} ({current["event"]}).',
                f'Fresh {"demand" if side=="BUY" else "supply"} zone: full wick range of the final consolidation candle before displacement.',
                f'Stop beyond zone by 10% of its width (minimum $0.01). Worst-zone entry reward/risk {rr:.2f}:1; minimum 2.5:1.',
                'TP3 = recent completed-candle high/low at creation; TP1/TP2 divide that distance into thirds, not fixed R multiples.',
                'First subsequent executable quote inside zone only; all-out at TP3 or stop. No time-based exit.']), 'Fresh structure-aligned zone ready for a retest.'
    return None, reason


def invalidate_pending(bars, now, signals):
    """Cancel only unfilled current-strategy setups after a closed structure change."""
    from .engine import aggregate
    cache = {}
    for signal in signals:
        if signal.get('strategy') != STRATEGY or signal['status'] != 'PENDING':
            continue
        tf = int(signal['timeframe'][1:])
        if tf not in cache:
            candles = contiguous_tail(aggregate(bars,tf*60,now),tf*60)
            cache[tf] = structure(candles)[-1] if len(candles)>=30 else dict(bias=None)
        state = cache[tf]
        if state and state['bias'] != signal['side']:
            signal.update(status='INVALIDATED',closed_at=now,
                          invalidation_reason='Completed candles invalidated the setup market structure.')
