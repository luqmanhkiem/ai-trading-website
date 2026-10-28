import copy
import pytest
from app.engine import Candle, aggregate, evaluate, advance, metrics, lot_size


def fixture_bars(direction=1, timeframe=5):
    values=[(100,101,99,100.1)]*106 + [
        (101,102,100,101),(102,104,101,103),(103,106,102,104),(104,105,101,102),
        (102,103,99,100),(100,102,97,99),(99,102,98,101),(101,104,100,103),
        (103,105,102,104),(104,108,103,107),(107,108,106,107.2),
        (107.2,108,106,107),(107,108,106,107.1),(107.1,119,107,118.5)]
    bars=[]
    for o,h,l,c in values:
        if direction < 0:o,h,l,c=300-o,300-l,300-h,300-c
        for _ in range(timeframe//5):
            bars.append(Candle(len(bars)*300,o,h,l,c))
    return bars


def test_completed_m15_only():
    bars=fixture_bars()
    result=aggregate(bars,900,120*300-1)
    assert result[-1].time==114*300
    assert len(result)==39
    assert aggregate(bars[:2],900,900)==[]

@pytest.mark.parametrize('direction,side',[(1,'BUY'),(-1,'SELL')])
def test_rules_and_levels(direction,side):
    signal,reason=evaluate(fixture_bars(direction),5,120*300)
    assert signal['side']==side
    assert signal['bar_time']==119*300
    assert (signal['entry']-signal['stop'])*direction > 0
    assert all((p-signal['entry'])*direction > 0 for p in signal['targets'])
    assert signal['status']=='PENDING'
    assert signal['strategy']=='structure-supply-demand-v1'
    assert signal['planned_rr']>=2.5


def test_flat_market_no_signal():
    bars=[Candle(i*300,100,101,99,100) for i in range(120)]
    assert evaluate(bars,5,36000)[0] is None


def new_signal():
    return evaluate(fixture_bars(),5,36000)[0]


def test_entry_expiry_and_no_fabricated_win():
    s=new_signal()
    advance(s,(s['entry_high']+s['targets'][0])/2,s['created_at']+1)
    assert s['status']=='PENDING'
    assert metrics([s])['win_rate'] is None
    advance(s,s['entry'],s['expires_at'])
    assert s['status']=='EXPIRED'
    assert metrics([s])['closed']==0


def test_fill_then_milestones_then_tp3():
    s=new_signal()
    advance(s,s['entry'],36001)
    assert s['status']=='OPEN'
    advance(s,s['targets'][0],36002)
    assert s['targets_hit']==1 and s['result_r'] is None
    advance(s,s['targets'][2]+100,36003)
    assert s['status']=='TP3'
    assert s['result_r']==pytest.approx((s['targets'][2]-s['entry'])/s['risk'],abs=.01)
    assert metrics([s])['win_rate']==100


def test_gap_stop_uses_worse_observed_quote():
    s=new_signal()
    advance(s,s['entry_high'],36001)
    advance(s,s['stop']-5,36002)
    assert s['status']=='STOPPED' and s['result_r'] < -1


def test_metrics_exclude_pending_and_use_closed_denominator():
    pending=new_signal()
    win=copy.deepcopy(pending);win.update(status='TP3',result_r=3)
    loss=copy.deepcopy(pending);loss.update(status='STOPPED',result_r=-1.5)
    flat=copy.deepcopy(pending);flat.update(status='STOPPED',result_r=0)
    m=metrics([win,loss,flat,pending])
    assert m['closed']==3 and m['win_rate']==33.3
    assert m['net_r']==1.5 and m['breakeven']==1


def test_lot_round_down_and_minimum():
    result=lot_size(10000,1,2680,2673,100,.01,.01,100)
    assert result['lots']==.14 and result['estimated_risk']==98
    assert lot_size(10,.1,2680,2673)['lots']==0
    assert lot_size(1000000,1,2680,2673,max_lot=.1)['lots']==.1

@pytest.mark.parametrize('change',[{'entry':2673},{'risk_percent':101},{'balance':float('nan')},{'lot_step':0},{'min_lot':2,'max_lot':1}])
def test_invalid_lot(change):
    args=dict(balance=10000,risk_percent=1,entry=2680,stop=2673)
    args.update(change)
    with pytest.raises(ValueError):lot_size(**args)

@pytest.mark.parametrize('direction', [1, -1])
def test_setup_profiles_use_distinct_timeframes_and_risk(direction):
    bars=fixture_bars(direction)
    scalp,_=evaluate(bars,5,36000)
    day_bars=fixture_bars(direction,15)
    day,_=evaluate(day_bars,15,len(day_bars)*300)
    assert scalp['profile']=='scalping' and day['profile']=='intraday'
    assert scalp['strategy'] == day['strategy']
    assert scalp['zone_id'] != day['zone_id']
    assert day['risk'] == scalp['risk']
    assert scalp['expires_at']-36000==900
    assert day['expires_at']-len(day_bars)*300==2700
    assert day['bar_time']==len(day_bars)*300-900  # completed M15, not an in-progress bucket
    assert '2.5:1' in day['explanation'][2]
    assert metrics([scalp,day])['win_rate'] is None


def test_unsupported_setup_timeframe_rejected():
    with pytest.raises(ValueError):evaluate(fixture_bars(),1,36000)
