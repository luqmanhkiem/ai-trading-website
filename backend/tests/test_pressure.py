from app.engine import Candle
from app.pressure import pressure_frame,pressure_snapshot

def bars():
 return [Candle(i*300,100,101,99,100.2) for i in range(400)]

def test_missing_and_stale_data_are_unavailable():
 assert pressure_frame([],15,120000)['status']=='unavailable'
 assert pressure_frame(bars(),15,140000)['status']=='unavailable'
 data=pressure_snapshot(bars(),120000,False)
 assert all(f['status']=='unavailable' and not f['evidence'] for f in data['frames'])
 assert data['pending_orders']=='unavailable' and data['tick_volume']=='unavailable'

def test_future_candles_do_not_change_reading():
 original=bars()
 before=pressure_frame(original,15,120000)
 assert before==pressure_frame(original+[Candle(120000,100,150,50,140)],15,120000)

def test_directional_evidence_is_not_probability(monkeypatch):
 monkeypatch.setattr('app.pressure.structure',lambda c:[dict(bias='SELL')]*len(c))
 monkeypatch.setattr('app.pressure.fair_value_gaps',lambda c:[dict(side='bearish',time=c[-1].time)])
 result=pressure_frame(bars(),15,120000)
 assert result['reading']=='Selling-pressure evidence' and result['sell_count']==2
 assert 'confidence' not in result
 monkeypatch.setattr('app.pressure.swing_sweeps',lambda *args:[dict(side='bullish',time=119000)])
 assert pressure_frame(bars(),15,120000)['reading']=='Mixed / inconclusive'

def test_unconfirmed_resistance_cannot_be_repeated_rejection(monkeypatch):
 monkeypatch.setattr('app.pressure.confirmed_swings',lambda c:[dict(kind='high',price=100,time=0,confirmed_at=999999)])
 result=pressure_frame(bars(),15,120000)
 assert all(e['kind']!='rejection' for e in result['evidence'])
