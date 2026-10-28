"""Confirmation gates must block missing evidence and never use an open candle."""
import copy
import pytest
from app.engine import Candle,advance
from app.reference_rules import reversal,confirmed_candidates,STRATEGY

@pytest.mark.parametrize('side,previous,bar,expected',[
 ('BUY',Candle(0,102,103,99,100),Candle(300,99,104,98,103),'engulfing'),
 ('SELL',Candle(0,100,103,99,102),Candle(300,103,104,98,99),'engulfing'),
 ('BUY',Candle(0,100,101,99,100),Candle(300,100,102,94,101),'pin bar'),
 ('SELL',Candle(0,100,101,99,100),Candle(300,101,107,99,100),'pin bar'),
 ('BUY',Candle(0,100,101,99,100),Candle(300,100,100,100,100),None),
 ('BUY',Candle(0,100,104,99,103),Candle(300,103,104,100,101),None),
])
def test_reversal_confirmation(side,previous,bar,expected):
 assert reversal(previous,bar,side)==expected

def setup(monkeypatch):
 bars=[Candle(i*300,100,102,98,101) for i in range(400)]
 bars[-2]=Candle(398*300,102,103,99,100)
 bars[-1]=Candle(399*300,99,104,98,103)
 zone=dict(side='BUY',zone_type='demand',entry=100,entry_low=99,entry_high=101,stop=97,
    zone_confirmed_at=100*300,zone_time=99*300,timeframe='M5',profile='scalping',expires_at=200000,
    status='PENDING',fill_price=None,filled_at=None,result_r=None,targets_hit=0)
 monkeypatch.setattr('app.reference_rules.structure',lambda candles:[{'bias':'BUY','protected':96}]*len(candles))
 monkeypatch.setattr('app.reference_rules.swing_sweeps',lambda candles,swings:[dict(side='bullish',time=candles[-2].time)])
 monkeypatch.setattr('app.reference_rules.zone_candidates',lambda *args:([copy.deepcopy(zone)],''))
 return bars

def test_confirmed_signal_requires_future_fill_and_two_R(monkeypatch):
 bars=setup(monkeypatch)
 signals,reason=confirmed_candidates(bars,5,120000)
 assert len(signals)==1 and 'future' in reason
 s=signals[0]
 assert s['strategy']==STRATEGY and s['status']=='PENDING' and s['fill_price'] is None
 assert s['stop']<96 and s['rr_targets']==[1,1.5,2]
 advance(s,100,120001)
 assert s['status']=='OPEN' and s['filled_rr']==2
 assert s['targets'][2]==round(100+2*(100-s['stop']),2)
 advance(s,s['targets'][2],120002)
 assert s['result_r']==2

@pytest.mark.parametrize('blocker',['alignment','sweep','zone','confirmation'])
def test_each_missing_confluence_blocks(monkeypatch,blocker):
 bars=setup(monkeypatch)
 if blocker=='alignment':monkeypatch.setattr('app.reference_rules.structure',lambda c:[dict(bias=None,protected=None)]*len(c))
 if blocker=='sweep':monkeypatch.setattr('app.reference_rules.swing_sweeps',lambda *args:[])
 if blocker=='zone':monkeypatch.setattr('app.reference_rules.zone_candidates',lambda *args:([],''))
 if blocker=='confirmation':bars[-1]=Candle(399*300,101,104,98,100)
 assert confirmed_candidates(bars,5,120000)[0]==[]

def test_short_history_and_open_candle_cannot_confirm(monkeypatch):
 bars=setup(monkeypatch)
 assert confirmed_candidates(bars[:100],5,120000)[0]==[]
 # Removing the last confirmation from the closed-bar set blocks it.
 assert confirmed_candidates(bars,5,119999)[0]==[]

def test_zone_identity_does_not_change_for_repeated_confirmation(monkeypatch):
 bars=setup(monkeypatch)
 first=confirmed_candidates(bars,5,120000)[0][0]
 bars.extend([Candle(120000,102,103,99,100),Candle(120300,99,104,98,103)])
 second=confirmed_candidates(bars,5,120600)[0][0]
 assert first['zone_id']==second['zone_id']

def test_pending_invalidates_on_alignment_loss_but_open_trade_keeps_stop(monkeypatch):
 from app.reference_rules import invalidate_confirmed_pending
 bars=setup(monkeypatch)
 pending=confirmed_candidates(bars,5,120000)[0][0]
 opened=copy.deepcopy(pending);opened['status']='OPEN'
 monkeypatch.setattr('app.reference_rules.structure',lambda c:[dict(bias='SELL',protected=110)]*len(c))
 invalidate_confirmed_pending(bars,120000,[pending,opened])
 assert pending['status']=='INVALIDATED' and pending['result_r'] is None
 assert opened['status']=='OPEN'
