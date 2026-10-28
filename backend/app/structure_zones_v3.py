"""Observable supply/demand zones with structure-derived targets and descriptive grades."""
from statistics import median
from .engine import aggregate
from .price_action import structure, find_zones, contiguous_tail
from .zone_risk import grade_zone

STRATEGY='supply-demand-structure-v3'


def candidate_zones(candles,states):
    strict={z['time'] for z in find_zones(candles,states,require_alignment=False)}
    zones=[]
    for i in range(14,len(candles)):
        b,base=candles[i],candles[i-1]
        typical=median(c.high-c.low for c in candles[i-14:i])
        span=b.high-b.low
        if typical<=0 or span<=0 or base.high<=base.low:continue
        # Include weaker one-candle bases/departures, explicitly graded High.
        if abs(base.close-base.open)>1.2*typical or abs(b.close-b.open)<typical:continue
        side='BUY' if b.close>b.open else 'SELL'
        qualifies=(b.close>base.high and b.close>=b.low+.65*span) if side=='BUY' else (b.close<base.low and b.close<=b.low+.35*span)
        if qualifies:
            zones.append(dict(index=i,low=round(base.low,2),high=round(base.high,2),side=side,
                time=base.time,confirmed_at=b.time,strong_base=base.time in strict))
    return zones


def structural_target(candles,side,low,high,departure):
    # Pivots are confirmed only once both right-hand candles have closed.
    levels=[]
    for i in range(max(2,len(candles)-96),len(candles)-2):
        b=candles[i]
        others=candles[i-2:i]+candles[i+1:i+3]
        if side=='BUY' and b.high>=high+.03 and all(b.high>c.high for c in others):
            levels.append((b.high,b.time))
        if side=='SELL' and b.low<=low-.03 and all(b.low<c.low for c in others):
            levels.append((b.low,b.time))
    if levels:
        level,time=min(levels) if side=='BUY' else max(levels)
        return round(level,2),'Nearest confirmed opposing swing',time
    since=candles[departure:]
    b=max(since,key=lambda c:c.high) if side=='BUY' else min(since,key=lambda c:c.low)
    level=round(b.high if side=='BUY' else b.low,2)
    if (side=='BUY' and level>=high+.03) or (side=='SELL' and level<=low-.03):
        return level,'Completed departure-leg extreme (no opposing swing available)',b.time
    return None,None,None


def scan_zones(bars,timeframe,now):
    candles=contiguous_tail(aggregate(bars,timeframe*60,now),timeframe*60)
    if len(candles)<30:
        return [],f'Warming up: 30 contiguous completed M{timeframe} candles required.'
    states=structure(candles)
    results=[]
    # Do not require alignment: unconfirmed/counter-structure zones are labeled High.
    for z in reversed(candidate_zones(candles,states)):
        i,side=z['index'],z['side']
        if len(candles)-1-i>48 or candles[i].time+timeframe*60*49<=now:continue
        direction=1 if side=='BUY' else -1
        low,high=z['low'],z['high']
        if high<=low:continue
        buffer=max(.01,round((high-low)*.1,2))
        stop=round(low-buffer if side=='BUY' else high+buffer,2)
        after=candles[i+1:]
        if any(b.low<=stop if side=='BUY' else b.high>=stop for b in after):continue
        # Count separate visits, not every candle within a single visit.
        retests=0;inside=False
        for b in after:
            touching=b.low<=high and b.high>=low
            if touching and not inside:retests+=1
            inside=touching
        entry=round((low+high)/2,2)
        target,target_method,target_time=structural_target(candles,side,low,high,i)
        if target is None:continue
        distance=(target-entry)*direction
        targets=[round(entry+direction*distance*f,2) for f in (1/3,2/3,1)]
        if len(set(targets))<3 or any((t-entry)*direction<=0 for t in targets):continue
        grade=grade_zone(entry,stop,distance,retests,states[-1]['bias']==side)
        if not z['strong_base']:
            grade['risk_label']='High'
            grade['risk_reasons'].append('Weaker one-candle base/departure; does not meet the strict consolidation pattern.')
        results.append(dict(profile='scalping' if timeframe==5 else 'intraday',strategy=STRATEGY,
            timeframe=f'M{timeframe}',bar_time=candles[-1].time,created_at=now,
            zone_id=f'{STRATEGY}:M{timeframe}:{z["time"]}:{side}',zone_time=z['time'],zone_confirmed_at=z['confirmed_at'],
            zone_type='demand' if side=='BUY' else 'supply',side=side,entry=entry,entry_low=low,entry_high=high,stop=stop,
            targets=targets,structural_targets=True,target_method=target_method,target_time=target_time,
            targets_basis='TP3 fixed at structure; TP1/TP2 use reference midpoint until filled',
            risk=round(abs(entry-stop),2),retests=retests,**grade,
            status='PENDING',filled_at=None,closed_at=None,fill_price=None,result_r=None,targets_hit=0,
            expires_at=(candles[i].time+timeframe*60*49),
            explanation=[f'M{timeframe} {side} {"demand" if side=="BUY" else "supply"} zone; full wick range before displacement.',
                f'{grade["risk_label"]} relative risk: '+ ' '.join(grade['risk_reasons']),
                'No minimum reward/risk filter. Retested and unconfirmed-structure zones are included with risk labels.',
                f'TP3 {target:.2f}: {target_method}. TP1/TP2 are one-third/two-thirds of the reference-entry distance; TP3 freezes at creation; TP1/TP2 rebase to actual fill.',
                'Stops remain beyond the zone. All-out at TP3 or stop; TP1/TP2 are milestones, not partial exits.']))
        if len(results)==6:break
    return results, f'{len(results)} valid zone(s) found; all risk grades included.' if results else 'No intact base/departure zones in the current lookback; no reward/risk filter is applied.'


def refresh_risk(signals,candidates):
    by_id={c['zone_id']:c for c in candidates}
    for s in signals:
        if s.get('strategy')!=STRATEGY or s['status']!='PENDING':continue
        c=by_id.get(s.get('zone_id'))
        if c:
            for key in ('risk_label','risk_reasons','planned_rr','retests','explanation'):
                s[key]=c[key]
