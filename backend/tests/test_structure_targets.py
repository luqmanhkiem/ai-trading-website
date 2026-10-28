import pytest
from app.engine import Candle,advance
from app.structure_zones_v3 import scan_zones, structural_target, STRATEGY
from test_engine import fixture_bars


@pytest.mark.parametrize('direction',[1,-1])
def test_structure_target_stays_fixed_and_milestones_follow_actual_fill(direction):
    zones,_=scan_zones(fixture_bars(direction),5,36000)
    s=zones[0]
    assert s['strategy']==STRATEGY and s['structural_targets']
    assert 'target_pips' not in s and 'minimum_rr' not in s
    before=list(s['targets']);fill=s['entry_high'] if direction==1 else s['entry_low']
    assert abs(s['targets'][2]-s['entry'])!=4
    advance(s,fill,36001,boundary_price=fill-direction*.1)
    assert s['status']=='OPEN' and s['targets'][2]==before[2]
    assert s['targets'][0]==round(fill+(before[2]-fill)/3,2)
    assert all((t-fill)*direction>0 for t in s['targets'])
    advance(s,s['targets'][2],36002)
    assert s['status']=='TP3'
    assert s['result_r']==pytest.approx((s['targets'][2]-fill)*direction/abs(fill-s['stop']),abs=.0001)


def test_nearest_confirmed_opposing_swing_is_selected():
    bars=[Candle(i*300,100,h,99,100) for i,h in enumerate([102,103,110,105,104,106,107,120,109,108])]
    target,method,time=structural_target(bars,'BUY',100,104,5)
    assert target==110 and time==600 and 'confirmed' in method


def test_fallback_extreme_is_explicitly_labeled():
    bars=fixture_bars()
    target,method,time=structural_target(bars,'BUY',106,108,len(bars)-1)
    assert target==119 and 'no opposing swing' in method


def test_unknown_target_is_not_invented():
    bars=[Candle(i*300,100,101,99,100) for i in range(30)]
    assert structural_target(bars,'BUY',102,103,25)==(None,None,None)
