import asyncio
import copy
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.storage import Store
from app.mt5 import MT5Market,BridgeInput

TOKEN='local-test-token-which-is-at-least-32-characters'
BASE=1800000000  # M15-aligned deterministic test clock; never used by the actual feed.

def payload(now=BASE+299):
    start=int(now)//300*300
    bars=[]
    for i in range(121):
        p=2000+i
        bars.append(dict(time=start-120*300+i*300,open=p,high=p+.4,low=p-.4,close=p+.2))
    return dict(symbol='XAUUSD.vx',broker='Valetax International',tick_time_ms=int(now*1000),bid=2120.2,ask=2120.3,
                server_utc_offset_seconds=7200,contract_size=100,lot_step=.01,min_lot=.01,max_lot=100,bars=bars)

def market(tmp_path,monkeypatch,now=BASE+299):
    monkeypatch.setattr('app.mt5.time.time',lambda:now)
    cfg=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/mt5.db',data_mode='mt5',mt5_bridge_token=TOKEN)
    store=Store(cfg.database_url,'mt5')
    return MT5Market(cfg,store),store,cfg

def send(m,p):return asyncio.run(m.ingest(BridgeInput(**p)))

def test_start_empty_and_no_bootstrap_performance(tmp_path,monkeypatch):
    m,store,_=market(tmp_path,monkeypatch)
    snap=m.snapshot()
    assert snap['mode']=='mt5' and snap['price'] is None and snap['candles']==[]
    send(m,payload())
    assert m.snapshot()['metrics']['total']==0
    assert m.snapshot()['bid']==2120.2 and m.snapshot()['ask']==2120.3
    store.close()

@pytest.mark.parametrize('change',[
    {'symbol':'XAUUSD.other'}, {'broker':'Other Broker'}, {'tick_time_ms':(BASE+100)*1000},
    {'tick_time_ms':(BASE+400)*1000}, {'ask':2000}, {'bid':float('inf')},
])
def test_reject_bad_source_quotes(tmp_path,monkeypatch,change):
    m,store,_=market(tmp_path,monkeypatch)
    p=payload();p.update(change)
    with pytest.raises(ValueError):send(m,p)
    assert m.price is None
    store.close()

def test_bad_candles_rejected(tmp_path,monkeypatch):
    m,store,_=market(tmp_path,monkeypatch)
    for kind in ('duplicate','future','ohlc','unaligned'):
        p=payload()
        if kind=='duplicate':p['bars'][-2]['time']=p['bars'][-1]['time']
        if kind=='future':p['bars'][-1]['time']+=300
        if kind=='ohlc':p['bars'][0]['low']=9999
        if kind=='unaligned':p['bars'][0]['time']+=1
        with pytest.raises(ValueError):send(m,p)
    store.close()

def test_duplicate_does_not_refresh_freshness(tmp_path,monkeypatch):
    m,store,_=market(tmp_path,monkeypatch)
    send(m,payload());old=m.last_update
    monkeypatch.setattr('app.mt5.time.time',lambda:BASE+305)
    assert send(m,payload())['accepted'] is False
    assert m.last_update==old
    store.close()

@pytest.mark.parametrize('session_gap',[False,True])
def test_new_closed_candle_generates_only_current_m5_setup(tmp_path,monkeypatch,session_gap):
    from app.zone_board import scan_zones as legacy_scan
    monkeypatch.setattr('app.service.scan_zones',legacy_scan)
    m,store,_=market(tmp_path,monkeypatch)
    from test_engine import fixture_bars
    p=payload()
    strategy=fixture_bars()
    # The departure candle is still forming at bootstrap, then closes on the next packet.
    offset=BASE-strategy[-1].time
    neutral=dict(open=100,high=101,low=99,close=100.1)
    p['bars']=[dict(time=offset-300,**neutral)]+[dict(b.json(),time=b.time+offset) for b in strategy]
    if session_gap:
        for bar in p['bars'][:75]:bar['time']-=300
    p['bid'],p['ask']=118.5,118.6
    send(m,p)
    monkeypatch.setattr('app.mt5.time.time',lambda:BASE+300)
    p['tick_time_ms']=(BASE+300)*1000
    p['bars'].append(dict(time=BASE+300,open=118.5,high=118.6,low=118.4,close=118.5))
    send(m,p)
    signal=next(s for s in m.signals if s['timeframe']=='M5' and s['entry']==107)
    assert signal['mode']=='mt5' and signal['status']=='PENDING'
    assert signal['rr_targets']==[1,2,3] and 'target_pips' not in signal
    monkeypatch.setattr('app.mt5.time.time',lambda:BASE+301)
    p['tick_time_ms']+=1000;p['bid'],p['ask']=107,107.1;send(m,p)
    assert signal['status']=='OPEN'
    assert signal['fill_price']==p['ask']
    store.close()

def test_stale_reconnect_invalidates_without_inventing_outcome(tmp_path,monkeypatch):
    m,store,_=market(tmp_path,monkeypatch)
    p=payload();send(m,p)
    m.signals=[dict(id='gap',created_at=BASE,status='OPEN',timeframe='M5',result_r=None)]
    monkeypatch.setattr('app.mt5.time.time',lambda:BASE+320)
    p['tick_time_ms']=(BASE+320)*1000
    p['bars'].append(dict(time=BASE+300,open=2120.2,high=2120.4,low=2120.1,close=2120.2))
    send(m,p)
    assert m.signals[0]['status']=='DATA_GAP'
    assert m.snapshot()['metrics']['closed']==0 and m.snapshot()['metrics']['data_gaps']==1
    store.close()

def test_separate_live_and_simulation_tables(tmp_path,monkeypatch):
    m,store,cfg=market(tmp_path,monkeypatch)
    send(m,payload())
    simulated=Store(cfg.database_url)
    assert simulated.load()==(None,[])
    restored=MT5Market(cfg,store)
    assert restored.price==m.price and restored.stale()
    simulated.close();store.close()

def test_ingest_auth_and_no_token_exposure(tmp_path,monkeypatch):
    _,store,cfg=market(tmp_path,monkeypatch);store.close()
    with TestClient(create_app(cfg)) as client:
        assert client.post('/api/mt5/ingest',json=payload()).status_code==401
        response=client.post('/api/mt5/ingest',headers={'Authorization':'Bearer '+TOKEN},json=payload())
        assert response.status_code==200 and response.json()['accepted']
        assert TOKEN not in client.get('/api/config').text
        assert TOKEN not in client.get('/api/snapshot').text

def test_live_credentials_required(tmp_path):
    cfg=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/blank.db',data_mode='mt5')
    with pytest.raises(RuntimeError,match='MT5_BRIDGE_TOKEN'):
        with TestClient(create_app(cfg)):pass


def test_regular_quote_preserves_last_rule_reason(tmp_path,monkeypatch):
    m,store,_=market(tmp_path,monkeypatch)
    p=payload();send(m,p)
    m.reasons={'M5':'Waiting for a fresh demand zone.','M15':'Reward/risk below minimum.'}
    monkeypatch.setattr('app.mt5.time.time',lambda:BASE+299.5)
    p['tick_time_ms']+=500;send(m,p)
    assert m.reasons['M5']=='Waiting for a fresh demand zone.'
    assert m.reasons['M15']=='Reward/risk below minimum.'
    store.close()
