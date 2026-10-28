"""Disclosed Katana concepts, implemented independently; hidden engine rules are unknown."""
from __future__ import annotations
from dataclasses import dataclass
from .engine import Candle, aggregate
from .market_analysis import confirmed_swings, swing_sweeps
from .price_action import contiguous_tail, structure
from .zone_board import scan_zones as zone_candidates

STRATEGY = 'aurum-mtf-confirmation-v5'

@dataclass(frozen=True)
class Rules:
    """These thresholds are Aurum assumptions, not verified Katana parameters."""
    minimum_bars: int = 30
    sweep_lookback: int = 12
    pin_wick_body: float = 2.0
    pin_close_fraction: float = 0.65
    stop_buffer_fraction: float = 0.1
    minimum_buffer: float = 0.01
    target_r: tuple[float, float, float] = (1.0, 1.5, 2.0)
    max_signals: int = 1

RULES = Rules()

def reversal(previous: Candle, bar: Candle, side: str, rules: Rules = RULES) -> str | None:
    """Require directional rejection; a zone touch alone does not authorize an entry."""
    span = bar.high - bar.low
    if span <= 0:
        return None
    body = abs(bar.close - bar.open)
    if side == 'BUY':
        engulfing = previous.close < previous.open and bar.close > bar.open and bar.open <= previous.close and bar.close >= previous.open
        pin = bar.close > bar.open and min(bar.open, bar.close) - bar.low >= rules.pin_wick_body * body and bar.close >= bar.low + rules.pin_close_fraction * span
    else:
        engulfing = previous.close > previous.open and bar.close < bar.open and bar.open >= previous.close and bar.close <= previous.open
        pin = bar.close < bar.open and bar.high - max(bar.open, bar.close) >= rules.pin_wick_body * body and bar.close <= bar.high - rules.pin_close_fraction * span
    return 'engulfing' if engulfing else 'pin bar' if pin else None

def confirmed_candidates(bars: list[Candle], timeframe: int, now: int, rules: Rules = RULES) -> tuple[list[dict], str]:
    frames = {tf: aggregate(bars, tf * 60, now) for tf in (timeframe, 15, 30, 60)}
    frames[timeframe] = contiguous_tail(frames[timeframe], timeframe*60)
    missing = [f'M{tf}' if tf != 60 else 'H1' for tf, values in frames.items() if len(values) < rules.minimum_bars]
    if missing:
        return [], 'Waiting for 30 completed candles (contiguous on entry timeframe) on ' + ', '.join(missing) + '.'
    if any(now-values[-1].time-tf*60 > tf*60 for tf,values in frames.items()):
        return [], 'Higher-timeframe context is stale; waiting for completed candles.'
    biases = {tf: structure(values)[-1]['bias'] for tf, values in frames.items()}
    side = biases[15]
    if side is None or biases[60] != side or biases[30] != side:
        return [], 'Waiting for M15, M30 and H1 structure to align.'
    candles = frames[timeframe]
    last, previous = candles[-1], candles[-2]
    pattern = reversal(previous, last, side, rules)
    if pattern is None:
        return [], 'MTF aligned; waiting for a closed pin bar or engulfing reversal at a zone.'
    sweeps = swing_sweeps(candles, confirmed_swings(candles))
    wanted = 'bullish' if side == 'BUY' else 'bearish'
    recent = [s for s in sweeps if s['side'] == wanted and s['time'] >= candles[-rules.sweep_lookback].time]
    if not recent:
        return [], 'MTF aligned; waiting for a recent confirmed-swing liquidity sweep.'
    candidates, _ = zone_candidates(bars, timeframe, now)
    results = []
    for zone in candidates:
        if zone['side'] != side or zone['zone_confirmed_at'] >= last.time:
            continue
        if last.low > zone['entry_high'] or last.high < zone['entry_low']:
            continue
        sweep = recent[-1]
        if sweep['time'] < zone['zone_time']:
            continue
        direction = 1 if side == 'BUY' else -1
        protected = structure(candles)[-1]['protected']
        levels = [zone['stop'], last.low if side == 'BUY' else last.high]
        if protected is not None:
            levels.append(protected)
        buffer = max(rules.minimum_buffer, (zone['entry_high']-zone['entry_low']) * rules.stop_buffer_fraction)
        stop = round(min(levels)-buffer if side == 'BUY' else max(levels)+buffer, 2)
        # Retest entry is published only after confirmation, never filled retrospectively.
        entry = zone['entry']
        risk = (entry-stop)*direction
        if risk <= 0:
            continue
        zone.update(strategy=STRATEGY, zone_id=f'{STRATEGY}:M{timeframe}:{zone["zone_time"]}:{side}',
            stop=stop, risk=risk, targets=[round(entry+direction*risk*r,2) for r in rules.target_r],
            rr_targets=list(rules.target_r), planned_rr=rules.target_r[-1],
            target_method='TP1=1R / TP2=1.5R / TP3=2R; rebase once on observed retest fill',
            targets_basis='Confirmed setup; future retest required. Preview uses midpoint.',
            confirmation=pattern, confirmation_time=last.time+timeframe*60,
            risk_label='Unrated',risk_label_note='No calibrated risk probability or Katana grade is available.',
            risk_reasons=['M15/M30/H1 alignment, recent swing sweep and zone reversal confirmed.'],
            explanation=['Independent implementation of disclosed Katana concepts; not its proprietary engine.',
                'M15, M30 and H1 confirmed structure agree.',
                f'Recent {wanted} sweep of a previously confirmed swing.',
                f'Closed {pattern} touches the {zone["zone_type"]} zone.',
                'Stop lies beyond the zone, rejection extreme and protected setup structure.',
                'Future zone retest required; no historical candle fill. TP3=2R, before costs.'])
        results.append(zone)
        if len(results) >= rules.max_signals:
            break
    return results, 'Confirmed setup; waiting for a future zone retest.' if results else 'MTF aligned; reversal must touch an intact supply/demand zone after a liquidity sweep.'


def invalidate_confirmed_pending(bars: list[Candle], now: int, signals: list[dict]) -> None:
    """An unfilled plan loses validity when the required higher structure changes."""
    from .price_action import invalidate_pending
    invalidate_pending(bars, now, signals)
    pending = [s for s in signals if s.get('strategy') == STRATEGY and s['status'] == 'PENDING']
    if not pending:
        return
    biases = []
    for tf in (15,30,60):
        candles = aggregate(bars,tf*60,now)
        biases.append(structure(candles)[-1]['bias'] if len(candles)>=RULES.minimum_bars else None)
    for signal in pending:
        if any(bias != signal['side'] for bias in biases):
            signal.update(status='INVALIDATED',closed_at=now,
                invalidation_reason='Required M15/M30/H1 structure alignment is no longer present.')
