import copy
import pytest
from app.engine import Candle, evaluate, advance, metrics
from app.price_action import structure, find_zones, invalidate_pending, STRATEGY
from test_engine import fixture_bars


def append(bars,o,h,l,c):
    bars.append(Candle(bars[-1].time+300,o,h,l,c))


@pytest.mark.parametrize('direction,side',[(1,'BUY'),(-1,'SELL')])
def test_full_wick_zone_structural_stop_and_recent_extreme(direction,side):
    bars=fixture_bars(direction)
    s,_=evaluate(bars,5,len(bars)*300)
    assert s['side']==side and s['strategy']==STRATEGY
    assert s['entry_low']==bars[-2].low and s['entry_high']==bars[-2].high
    assert s['targets'][2]==(bars[-1].high if direction==1 else bars[-1].low)
    assert s['stop']==pytest.approx(s['entry_low']-.2 if direction==1 else s['entry_high']+.2)
    worst=s['entry_high'] if direction==1 else s['entry_low']
    assert (s['targets'][2]-worst)*direction/abs(worst-s['stop'])>=2.5
    assert s['targets'][0]==pytest.approx(s['entry']+(s['targets'][2]-s['entry'])/3)


def test_pivots_confirm_late_and_unvalidated_internal_low_does_not_flip():
    bars=fixture_bars()
    states=structure(bars)
    assert states[111]['bias'] is None  # pullback not yet followed by an external break
    assert states[115]['bias']=='BUY' and states[115]['protected']==97
    for values in [(118,119,114,115),(115,117,110,112),(112,116,111,115),
                   (115,118,113,117),(117,118,108,109)]:append(bars,*values)
    assert structure(bars)[-1]['bias']=='BUY'
    assert structure(bars)[-1]['protected']==97
    append(bars,109,110,95,96)
    assert structure(bars)[-1]['bias']=='SELL'
    assert structure(bars)[-1]['event']=='CHoCH'


def test_higher_high_validates_a_confirmed_higher_low():
    bars=fixture_bars()
    for v in [(118,119,114,115),(115,118,115,117),(117,118,110,112),(112,116,111,115),
              (115,118,113,117),(117,120,116,119),(119,122,118,121)]:append(bars,*v)
    state=structure(bars)[-1]
    assert state['bias']=='BUY' and state['protected']==110 and state['event']=='BOS'


def test_incomplete_departure_is_not_a_signal_and_future_data_does_not_leak():
    bars=fixture_bars()
    cutoff=(len(bars)-1)*300
    assert evaluate(bars,5,cutoff)[0] is None
    original=evaluate(bars,5,len(bars)*300)
    future=copy.deepcopy(bars)
    append(future,118,200,50,150)
    assert evaluate(future,5,len(bars)*300)==original


def test_reward_risk_filter_rejects_even_a_valid_zone():
    bars=fixture_bars()
    bars[-1]=Candle(bars[-1].time,107.1,113,107,112.9)
    assert find_zones(bars,structure(bars))
    s,reason=evaluate(bars,5,len(bars)*300)
    assert s is None and 'minimum 2.5:1' in reason


@pytest.mark.parametrize('last',[(118,120,107,119),(118,119,104,105)])
def test_previously_touched_or_gapped_zone_is_not_reissued(last):
    bars=fixture_bars();append(bars,*last)
    assert evaluate(bars,5,len(bars)*300)[0] is None


def test_monotonic_breakout_without_structure_or_base_does_not_force_trade():
    bars=[Candle(i*300,100+i,101+i,99+i,100.8+i) for i in range(120)]
    assert evaluate(bars,5,36000)[0] is None


@pytest.mark.parametrize('which',['stop','target'])
def test_pre_entry_stop_or_target_invalidates_without_fabricated_result(which):
    s=evaluate(fixture_bars(),5,36000)[0]
    advance(s,s['stop'] if which=='stop' else s['targets'][2],36001)
    assert s['status']=='INVALIDATED' and s['fill_price'] is None
    assert metrics([s])['closed']==0


def test_executable_fill_checks_reward_risk_and_preserves_target():
    s=evaluate(fixture_bars(),5,36000)[0]
    s['targets']=[108,109,110]  # A changed/older target cannot bypass fill-time RR.
    advance(s,s['entry_high'],36001)
    assert s['status']=='PENDING'
    advance(s,s['entry_low'],36002)
    assert s['status']=='OPEN' and s['fill_price']==s['entry_low']
    assert s['targets'][2]==110


def test_structure_change_invalidates_pending_but_never_rewrites_open_or_legacy():
    bars=fixture_bars();s=evaluate(bars,5,36000)[0]
    pending=copy.deepcopy(s);opened=copy.deepcopy(s);opened['status']='OPEN'
    legacy=copy.deepcopy(s);legacy['strategy']='scalping-breakout-ema-atr-v2'
    append(bars,118,119,95,96)
    invalidate_pending(bars,36300,[pending,opened,legacy])
    assert pending['status']=='INVALIDATED'
    assert opened['status']=='OPEN' and legacy['status']=='PENDING'
    assert opened['stop']==s['stop'] and legacy['targets']==s['targets']


def test_session_gap_requires_new_contiguous_structure():
    bars=fixture_bars();bars[-1].time+=300
    assert evaluate(bars,5,36300)[0] is None


def test_consumed_zone_is_not_reused_after_expiry_or_restart(tmp_path,monkeypatch):
    from app.zone_board import scan_zones as legacy_scan
    monkeypatch.setattr('app.service.scan_zones',legacy_scan)
    from app.config import Settings
    from app.storage import Store
    from app.service import Market
    cfg=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/zones.db')
    store=Store(cfg.database_url)
    m=Market(cfg,store);m.bars=fixture_bars();m.now=36000;m.signals=[]
    m.check_signals()
    count=len(m.signals)
    assert count>0
    for s in m.signals:s.update(status='EXPIRED',closed_at=36001)
    m.persist()
    restored=Market(cfg,store)
    restored.check_signals()
    assert len(restored.signals)==count
    assert restored.signals[0]['zone_id']==m.signals[0]['zone_id']
    store.close()


def test_bearish_protected_high_survives_internal_break_then_changes_direction():
    bars=fixture_bars(-1)
    assert structure(bars)[-1]['protected']==203
    append(bars,181,192,180,191)
    assert structure(bars)[-1]['bias']=='SELL'
    append(bars,191,205,190,204)
    assert structure(bars)[-1]['bias']=='BUY'
    assert structure(bars)[-1]['event']=='CHoCH'


def test_old_untouched_zone_ages_out():
    bars=fixture_bars()
    for _ in range(13):append(bars,117,118,116,117.1)
    assert evaluate(bars,5,len(bars)*300)[0] is None


@pytest.mark.parametrize('direction',[1,-1])
def test_spread_does_not_falsely_cancel_a_pending_target(direction):
    s=evaluate(fixture_bars(direction),5,36000)[0]
    target=s['targets'][2]
    # Entry-side quote crosses target; executable exit side has not reached it.
    advance(s,target+direction*.2,36001,boundary_price=target-direction*.1)
    assert s['status']=='PENDING'
    advance(s,target+direction*.3,36002,boundary_price=target)
    assert s['status']=='INVALIDATED' and s['invalidation_code']=='TARGET_BEFORE_ENTRY'
    assert s['invalidation_price']==target and s['invalidation_level']==target
    assert 'No paper entry filled' in s['invalidation_reason']


@pytest.mark.parametrize('direction',[1,-1])
def test_pending_stop_uses_executable_exit_side(direction):
    s=evaluate(fixture_bars(direction),5,36000)[0]
    advance(s,s['stop']+direction*.1,36001,boundary_price=s['stop'])
    assert s['status']=='INVALIDATED' and s['invalidation_code']=='ZONE_STOP_BEFORE_ENTRY'
    assert s['fill_price'] is None and s['result_r'] is None
