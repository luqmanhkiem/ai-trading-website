"""Deterministic closed-bar rules and conservative, tick-based paper accounting."""
from dataclasses import dataclass, asdict
from math import floor, isfinite
from typing import List

@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float

    def json(self):
        return asdict(self)

def aggregate(bars: List[Candle], seconds: int, before: int):
    """Only return complete time buckets; never use a partially formed M15 bar."""
    groups = {}
    for b in bars:
        start = b.time // seconds * seconds
        if start + seconds > before:
            continue
        groups.setdefault(start, []).append(b)
    result = []
    for start, group in sorted(groups.items()):
        # M5 base bars must cover the entire bucket (also protects warm-up edge).
        if len(group) != seconds // 300 or group[0].time != start:
            continue
        result.append(Candle(start, group[0].open, max(b.high for b in group), min(b.low for b in group), group[-1].close))
    return result

def evaluate(bars, timeframe, now):
    from .price_action import evaluate_candles
    if timeframe not in (5, 15):
        raise ValueError('Supported setup timeframes are M5 and M15.')
    return evaluate_candles(aggregate(bars,timeframe*60,now),timeframe,now)


def advance(signal, price, timestamp, boundary_price=None):
    """A quote that fills cannot also close. Out-of-zone gaps never count as fills."""
    if signal['status'] == 'PENDING':
        if timestamp >= signal['expires_at']:
            signal.update(status='EXPIRED', closed_at=timestamp)
        elif signal.get('rr_targets'):
            direction=1 if signal['side']=='BUY' else -1
            boundary=price if boundary_price is None else boundary_price
            if (boundary-signal['stop'])*direction<=0:
                signal.update(status='INVALIDATED',closed_at=timestamp,invalidation_code='ZONE_STOP_BEFORE_ENTRY',
                    invalidation_price=boundary,invalidation_level=signal['stop'],
                    invalidation_reason=f'Zone stop boundary broken before entry: exit-side quote {boundary:.2f}, stop {signal["stop"]:.2f}.')
            elif signal['entry_low']<=price<=signal['entry_high'] and (price-signal['stop'])*direction>0:
                risk=abs(price-signal['stop'])
                signal.update(status='OPEN',filled_at=timestamp,fill_price=price,risk=risk,
                    targets=[round(price+direction*risk*n,2) for n in signal['rr_targets']],
                    targets_basis='Actual entry-to-stop risk: '+', '.join(f'TP{i+1}={r:g}R' for i,r in enumerate(signal['rr_targets'])),filled_rr=float(signal['rr_targets'][-1]))
        elif signal.get('structural_targets'):
            direction=1 if signal['side']=='BUY' else -1
            boundary=price if boundary_price is None else boundary_price
            if (boundary-signal['stop'])*direction<=0:
                signal.update(status='INVALIDATED',closed_at=timestamp,invalidation_code='ZONE_STOP_BEFORE_ENTRY',
                    invalidation_price=boundary,invalidation_level=signal['stop'],
                    invalidation_reason=f'Zone stop boundary broken before entry: exit-side quote {boundary:.2f}, stop {signal["stop"]:.2f}.')
            elif signal['entry_low']<=price<=signal['entry_high'] and (price-signal['stop'])*direction>0:
                final=signal['targets'][2]
                signal.update(status='OPEN',filled_at=timestamp,fill_price=price,
                    targets=[round(price+(final-price)*f,2) for f in (1/3,2/3,1)],
                    targets_basis='TP3 fixed at structure; TP1/TP2 measured from actual fill',
                    filled_rr=round(abs(final-price)/abs(price-signal['stop']),3))
        elif signal.get('target_pips'):
            direction=1 if signal['side']=='BUY' else -1
            boundary=price if boundary_price is None else boundary_price
            if (boundary-signal['stop'])*direction<=0:
                signal.update(status='INVALIDATED',closed_at=timestamp,invalidation_code='ZONE_STOP_BEFORE_ENTRY',
                    invalidation_price=boundary,invalidation_level=signal['stop'],
                    invalidation_reason=f'Zone stop boundary broken before entry: exit-side quote {boundary:.2f}, stop {signal["stop"]:.2f}.')
            elif signal['entry_low']<=price<=signal['entry_high'] and (price-signal['stop'])*direction>0:
                signal.update(status='OPEN',filled_at=timestamp,fill_price=price,
                    targets=[round(price+direction*p*signal['pip_size'],2) for p in signal['target_pips']],
                    targets_basis='actual observed fill',risk=round(abs(price-signal['stop']),2))
                signal['filled_rr']=round(abs(signal['targets'][2]-price)/abs(price-signal['stop']),3)
        elif signal.get('minimum_rr'):
            # The target/stop is executable on the exit side, independently of entry.
            boundary = price if boundary_price is None else boundary_price
            direction = 1 if signal['side']=='BUY' else -1
            stopped = (boundary-signal['stop'])*direction <= 0
            targeted = (boundary-signal['targets'][2])*direction >= 0
            if stopped or targeted:
                code = 'ZONE_STOP_BEFORE_ENTRY' if stopped else 'TARGET_BEFORE_ENTRY'
                level = signal['stop'] if stopped else signal['targets'][2]
                signal.update(status='INVALIDATED',closed_at=timestamp,invalidation_code=code,
                    invalidation_price=boundary,invalidation_level=level,
                    invalidation_reason=f'{"Stop boundary broken" if stopped else "TP3 reached"} before entry: exit-side quote {boundary:.2f}, level {level:.2f}. No paper entry filled.')
                return
            if signal['entry_low'] <= price <= signal['entry_high']:
                reward = (signal['targets'][2]-price)*direction
                risk = (price-signal['stop'])*direction
                if risk > 0 and reward/risk >= signal['minimum_rr']:
                    signal.update(status='OPEN',filled_at=timestamp,fill_price=price)
        elif signal['entry_low'] <= price <= signal['entry_high']:
            signal.update(status='OPEN', filled_at=timestamp, fill_price=price)
        return
    if signal['status'] != 'OPEN':
        return
    direction = 1 if signal['side'] == 'BUY' else -1
    stopped = (price-signal['stop'])*direction <= 0
    targets = sum((price-t)*direction >= 0 for t in signal['targets'])
    signal['targets_hit'] = max(signal['targets_hit'], targets)
    if stopped or targets == 3:
        # Use observed quote for stop slippage; cap favorable TP3 fills at limit.
        exit_price = price if stopped else signal['targets'][2]
        denominator = abs(signal['fill_price']-signal['stop'])
        signal.update(status='STOPPED' if stopped else 'TP3', closed_at=timestamp, exit_price=exit_price,
                      result_r=round((exit_price-signal['fill_price'])*direction/denominator,4),
                      result_pips=round((exit_price-signal['fill_price'])*direction/0.1,2))

def realized_pips(signal):
    """Use observed fill/exit prices; missing history never becomes a fabricated zero."""
    if signal.get('status') not in ('STOPPED','TP3'):
        return None
    fill, exit_price = signal.get('fill_price'), signal.get('exit_price')
    if fill is None or exit_price is None:
        return None
    direction = 1 if signal['side'] == 'BUY' else -1
    return round((exit_price-fill)*direction/0.1,2)

def metrics(signals):
    closed = [s for s in signals if s['status'] in ('STOPPED','TP3')]
    wins = sum(s['result_r'] > 0 for s in closed)
    total = sum(s['result_r'] for s in closed)
    pips = [value for signal in closed if (value := realized_pips(signal)) is not None]
    return dict(net_pips=round(sum(pips),2), average_pips=round(sum(pips)/len(pips),2) if pips else None,
                pips_count=len(pips), pip_size=0.1, closed=len(closed), wins=wins, losses=sum(s['result_r'] < 0 for s in closed),
                breakeven=sum(s['result_r'] == 0 for s in closed), win_rate=round(wins/len(closed)*100,1) if closed else None,
                net_r=round(total,2), average_r=round(total/len(closed),2) if closed else None,
                pending=sum(s['status']=='PENDING' for s in signals), open=sum(s['status']=='OPEN' for s in signals),
                expired=sum(s['status']=='EXPIRED' for s in signals), total=len(signals))

def lot_size(balance, risk_percent, entry, stop, contract_size=100, lot_step=0.01, min_lot=0.01, max_lot=100):
    values = (balance,risk_percent,entry,stop,contract_size,lot_step,min_lot,max_lot)
    if not all(isfinite(v) and v > 0 for v in values) or risk_percent > 100 or entry == stop or min_lot > max_lot:
        raise ValueError('Use positive finite values, risk ≤ 100%, different entry/stop, and min ≤ max lot.')
    cash = balance*risk_percent/100
    per_lot = abs(entry-stop)*contract_size
    lots = min(floor((cash/per_lot+1e-10)/lot_step)*lot_step, floor(max_lot/lot_step)*lot_step)
    lots = round(lots,8) if lots+1e-10 >= min_lot else 0
    return dict(lots=lots, risk_budget=round(cash,2), estimated_risk=round(lots*per_lot,2),
                unused_risk=round(cash-lots*per_lot,2), contract_size=contract_size,
                note='USD account; excludes spread, commission and slippage. Confirm broker contract size and lot limits.')
