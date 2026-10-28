import copy
import pytest
from app.engine import Candle, advance
from app.fixed_pip_zones import scan_zones, STRATEGY, refresh_risk
from app.zone_risk import grade_zone
from test_engine import fixture_bars


@pytest.mark.parametrize('direction',[1,-1])
def test_fixed_pips_and_rebase_to_actual_fill(direction):
    zones,_=scan_zones(fixture_bars(direction),5,36000)
    s=zones[0]
    assert s['strategy']==STRATEGY and 'minimum_rr' not in s
    assert s['target_pips']==[30,35,40] and s['pip_size']==.1
    fill=s['entry_high'] if direction==1 else s['entry_low']
    advance(s,fill,36001,boundary_price=fill-direction*.1)
    assert s['status']=='OPEN'
    assert s['targets']==[round(fill+direction*d,2) for d in (3,3.5,4)]
    assert s['targets_basis']=='actual observed fill'
    advance(s,s['targets'][2],36002)
    assert s['status']=='TP3'
    assert s['result_r']==pytest.approx(4/abs(fill-s['stop']),abs=.0001)


def test_high_risk_is_shown_instead_of_filtered():
    bars=fixture_bars()
    # Scale price geometry, keeping the $4 target fixed: no RR gate may hide this zone.
    bars=[Candle(b.time,b.open*10,b.high*10,b.low*10,b.close*10) for b in bars]
    zones,_=scan_zones(bars,5,36000)
    assert zones and zones[0]['risk_label']=='High'
    assert zones[0]['planned_rr']<.75
    assert 'minimum_rr' not in zones[0]


def test_projected_target_touch_before_entry_does_not_cancel():
    s=scan_zones(fixture_bars(),5,36000)[0][0]
    advance(s,s['targets'][2]+10,36001)
    assert s['status']=='PENDING'
    advance(s,s['entry_high'],36002)
    assert s['status']=='OPEN'


def test_retested_zone_remains_visible_but_stop_broken_zone_does_not():
    bars=fixture_bars()
    bars.append(Candle(36000,118,119,107,118))
    zones,_=scan_zones(bars,5,36300)
    assert zones and zones[0]['retests']==1 and zones[0]['risk_label']=='Mid'
    bars.append(Candle(36300,118,119,104,105))
    assert zones[0]['zone_id'] not in {z['zone_id'] for z in scan_zones(bars,5,36600)[0]}


@pytest.mark.parametrize('rr,visits,aligned,label',[(2,0,True,'Low'),(2,1,True,'Mid'),(1,0,True,'Mid'),(.5,0,True,'High'),(2,2,True,'High'),(2,0,False,'High')])
def test_grade_is_descriptive_not_a_filter(rr,visits,aligned,label):
    g=grade_zone(100,100-4/rr,4,visits,aligned)
    assert g['risk_label']==label
    assert 'not a win probability' in g['risk_label_note']


def test_multiple_zones_can_be_recorded_on_one_timeframe(tmp_path,monkeypatch):
    from app.service import Market
    from app.config import Settings
    from app.storage import Store
    cfg=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/multi.db')
    store=Store(cfg.database_url);m=Market(cfg,store)
    from app.zone_board import scan_zones as current_scan
    prototype=current_scan(fixture_bars(),5,36000)[0][0]
    candidates=[]
    for n in range(8):
        s=copy.deepcopy(prototype);s['zone_id']=f'zone:{n}';candidates.append(s)
    monkeypatch.setattr('app.service.scan_zones',lambda bars,tf,now:(copy.deepcopy(candidates) if tf==5 else [],'zones'))
    m.signals=[];m.check_signals()
    assert len(m.signals)==6
    m.check_signals();assert len(m.signals)==6
    assert len({s['zone_id'] for s in m.signals})==6
    store.close()


def test_current_retest_risk_refreshes_pending_zone():
    prototype=scan_zones(fixture_bars(),5,36000)[0][0]
    pending=copy.deepcopy(prototype)
    prototype.update(risk_label='High',retests=2,risk_reasons=['Two retests'])
    refresh_risk([pending],[prototype])
    assert pending['risk_label']=='High' and pending['retests']==2


def test_live_stop_invalidates_pending_even_without_minimum_rr():
    s=scan_zones(fixture_bars(),5,36000)[0][0]
    advance(s,s['entry_low'],36001,boundary_price=s['stop'])
    assert s['status']=='INVALIDATED' and s['invalidation_code']=='ZONE_STOP_BEFORE_ENTRY'
    assert s['fill_price'] is None


def test_weaker_departure_is_included_and_explicitly_high_risk():
    bars=fixture_bars()
    bars[-1]=Candle(bars[-1].time,107.1,111.5,107,111.4)
    zones,_=scan_zones(bars,5,36000)
    assert zones[0]['risk_label']=='High'
    assert any('Weaker' in r for r in zones[0]['risk_reasons'])
