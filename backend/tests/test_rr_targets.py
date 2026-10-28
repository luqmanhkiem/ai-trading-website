import copy
import pytest
from app.engine import advance
from app.zone_board import scan_zones,STRATEGY
from test_engine import fixture_bars


@pytest.mark.parametrize('side,stop,fill,targets',[
    ('BUY',4195,4200,[4205,4210,4215]),
    ('SELL',4205,4200,[4195,4190,4185]),
    ('BUY',4195,4201,[4207,4213,4219]),
    ('SELL',4205,4199,[4193,4187,4181]),
])
def test_targets_use_actual_fill_and_original_stop(side,stop,fill,targets):
    s=dict(status='PENDING',rr_targets=[1,2,3],side=side,stop=stop,entry_low=4198,entry_high=4202,
           targets=[0,0,0],expires_at=100,targets_hit=0,result_r=None)
    advance(s,fill,1)
    assert s['status']=='OPEN' and s['targets']==targets and s['stop']==stop
    advance(s,targets[2],2)
    assert s['status']=='TP3' and s['result_r']==3


@pytest.mark.parametrize('direction',[1,-1])
def test_scanner_previews_midpoint_R_then_rebases_once(direction):
    s=scan_zones(fixture_bars(direction),5,36000)[0][0]
    assert s['strategy']==STRATEGY and s['rr_targets']==[1,2,3]
    assert 'structural_targets' not in s and 'target_pips' not in s
    ref=abs(s['entry']-s['stop'])
    assert s['targets']==[round(s['entry']+direction*ref*n,2) for n in (1,2,3)]
    fill=s['entry_high'] if direction==1 else s['entry_low']
    advance(s,fill,36001,boundary_price=fill-direction*.1)
    risk=abs(fill-s['stop']);targets=list(s['targets'])
    assert targets==[round(fill+direction*risk*n,2) for n in (1,2,3)]
    advance(s,fill+direction*risk*.5,36002)
    assert s['targets']==targets and s['status']=='OPEN'


def test_projected_target_touch_does_not_cancel_and_stop_break_does():
    s=scan_zones(fixture_bars(),5,36000)[0][0]
    advance(s,s['targets'][2]+10,36001)
    assert s['status']=='PENDING'
    advance(s,s['stop'],36002)
    assert s['status']=='INVALIDATED' and s['result_r'] is None


def test_legacy_structural_targets_are_not_converted_to_R():
    from app.structure_zones_v3 import scan_zones as old_scan
    s=old_scan(fixture_bars(),5,36000)[0][0]
    original=copy.deepcopy(s)
    advance(s,s['entry'],36001)
    assert s['targets'][2]==original['targets'][2]
    assert 'rr_targets' not in s
