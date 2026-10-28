"""Explainable closed-candle tools. No proprietary ML, order flow or probabilities."""
from .engine import aggregate
from .price_action import structure,contiguous_tail

TIMEFRAMES=(('M5',300),('M15',900),('M30',1800),('H1',3600),('D1',86400))


def confirmed_swings(candles):
    result=[]
    seconds=candles[1].time-candles[0].time if len(candles)>1 else 300
    for i in range(2,len(candles)-2):
        b=candles[i];neighbors=candles[i-2:i]+candles[i+1:i+3]
        if all(b.high>c.high for c in neighbors):result.append(dict(kind='high',price=b.high,time=b.time,confirmed_at=candles[i+2].time+seconds))
        if all(b.low<c.low for c in neighbors):result.append(dict(kind='low',price=b.low,time=b.time,confirmed_at=candles[i+2].time+seconds))
    return result


def fair_value_gaps(candles):
    """Three-candle wick imbalance; later full wick fill mitigates it."""
    result=[]
    for i in range(2,len(candles)):
        a,c=candles[i-2],candles[i]
        if c.low>a.high:side,low,high='bullish',a.high,c.low
        elif c.high<a.low:side,low,high='bearish',c.high,a.low
        else:continue
        later=candles[i+1:]
        filled=any(b.low<=low for b in later) if side=='bullish' else any(b.high>=high for b in later)
        if filled:continue
        partial=any(b.low<high for b in later) if side=='bullish' else any(b.high>low for b in later)
        result.append(dict(side=side,low=low,high=high,time=c.time,partial=partial))
    return result[-12:]


def swing_sweeps(candles,swings):
    """A wick beyond the latest previously-confirmed swing, closing back inside."""
    result=[]
    for b in candles[-60:]:
        known=[s for s in swings if s['confirmed_at']<=b.time]
        for kind in ('high','low'):
            candidates=[s for s in known if s['kind']==kind]
            if not candidates:continue
            s=candidates[-1]
            swept=b.high>s['price'] and b.close<s['price'] if kind=='high' else b.low<s['price'] and b.close>s['price']
            if swept:result.append(dict(side='bearish' if kind=='high' else 'bullish',time=b.time,price=s['price'],swing_time=s['time']))
    return result[-12:]


def possible_zones(candles):
    """Base/displacement areas remain candidates until price breaks their distal edge."""
    from .zone_board import candidate_zones
    if len(candles)<30:
        return []
    zones=[]
    for zone in candidate_zones(candles,structure(candles)):
        if len(candles)-1-zone['index']>48:
            continue
        later=candles[zone['index']+1:]
        broken=any(b.low<zone['low'] for b in later) if zone['side']=='BUY' else any(b.high>zone['high'] for b in later)
        if broken:
            continue
        touches=sum(b.low<=zone['high'] and b.high>=zone['low'] for b in later)
        zones.append(dict(side=zone['side'],kind='demand' if zone['side']=='BUY' else 'supply',
            low=zone['low'],high=zone['high'],time=zone['time'],confirmed_at=zone['confirmed_at'],
            tested=touches>0,method='One-candle base before displacement; possible reaction area, not a confirmed entry.'))
    price=candles[-1].close
    nearest=[]
    for side in ('BUY','SELL'):
        candidates=[z for z in zones if z['side']==side]
        nearest.extend(sorted(candidates,key=lambda z:abs((z['low']+z['high'])/2-price))[:2])
    return sorted(nearest,key=lambda z:z['time'])


def analyze_timeframe(bars,seconds,now):
    candles=aggregate(bars,seconds,now)
    if seconds==300:candles=contiguous_tail(candles,seconds)
    count=len(candles)
    ready=count>=30
    states=structure(candles) if ready else []
    latest=states[-1] if states else dict(bias=None,protected=None,event=None)
    swings=confirmed_swings(candles)
    events=[]
    for i in range(1,len(states)):
        previous,state=states[i-1],states[i]
        if state['bias'] and (state['bias']!=previous['bias'] or state['protected']!=previous['protected']):
            events.append(dict(kind=state['event'],side=state['bias'],price=candles[i].close,time=candles[i].time,protected=state['protected']))
    return dict(ready=ready,bar_count=count,required_bars=30,
        reason='Observed completed candles only; higher contexts may cross session gaps.' if ready else f'Need 30 completed candles; {count} available.',
        bias='bullish' if latest['bias']=='BUY' else 'bearish' if latest['bias']=='SELL' else 'neutral' if ready else 'unavailable',
        protected=latest['protected'],structure_event=latest['event'],events=events[-12:],swings=swings[-20:],
        zones=possible_zones(candles),gaps=fair_value_gaps(candles),sweeps=swing_sweeps(candles,swings),candles=[b.json() for b in candles[-100:]],
        last_close=candles[-1].close if candles else None,updated_at=candles[-1].time+seconds if candles else None)


class AnalysisService:
    def __init__(self):self.key=None;self.cached=None

    def snapshot(self,bars,now):
        key=(now//300,tuple((b.time,b.open,b.high,b.low,b.close) for b in bars))
        if self.key==key:return self.cached
        frames={name:analyze_timeframe(bars,seconds,now) for name,seconds in TIMEFRAMES}
        frames['M1']=dict(ready=False,bar_count=0,required_bars=30,bias='unavailable',protected=None,events=[],swings=[],gaps=[],sweeps=[],candles=[],last_close=None,updated_at=None,
            reason='Current broker bridge supplies M5 bars. M1 cannot be reconstructed from M5 OHLC.')
        self.cached=dict(timeframes=['M1']+[name for name,_ in TIMEFRAMES],by_timeframe=frames,
            alignment={name:sum(f['bias']==name for f in frames.values()) for name in ('bullish','bearish','neutral','unavailable')},
            limitations=['OHLC-based context; no exchange order book, institutional identities or true order-flow data.',
                'Swing pivots require two completed candles on each side. FVG and sweep definitions are mechanical heuristics.',
                'Agreement is not a win probability. Current confirmation setups require M15/M30/H1 agreement.'])
        self.key=key
        return self.cached
