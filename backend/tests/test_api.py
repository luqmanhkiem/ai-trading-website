from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.service import Market
from app.storage import Store
import pytest


def config(tmp_path,**kwargs):
    return Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/test.db',tick_seconds=60,**kwargs)


def test_rest_socket_and_persistence(tmp_path):
    cfg=config(tmp_path)
    with TestClient(create_app(cfg)) as client:
        assert client.get('/api/health').json()['status']=='ok'
        snap=client.get('/api/snapshot').json()
        assert snap['mode']=='simulated' and len(snap['candles'])>30
        assert snap['metrics']['closed']==0 and snap['metrics']['win_rate'] is None
        assert client.get('/api/news').json()['events']==[]
        with client.websocket_connect('/api/ws',headers={'origin':'http://localhost:5173'}) as ws:
            assert ws.receive_json()['price']==snap['price']
        assert client.post('/api/calculate-lot',json={'balance':10000,'risk_percent':1,'entry':2680,'stop':2675}).json()['lots']==.2
        assert client.post('/api/calculate-lot',json={'balance':10000,'risk_percent':1,'entry':2680,'stop':2680}).status_code==422
    with TestClient(create_app(cfg)) as client:
        assert client.get('/api/snapshot').json()['price']==snap['price']
        assert len(client.get('/api/signals').json())==len(snap['signals'])


def test_no_secret_leak_and_origin_rejection(tmp_path):
    cfg=config(tmp_path,telegram_bot_token='sensitive-test-token',telegram_chat_id='123')
    with TestClient(create_app(cfg)) as client:
        assert 'sensitive-test-token' not in client.get('/api/config').text
        with pytest.raises(Exception):
            with client.websocket_connect('/api/ws',headers={'origin':'https://untrusted.invalid'}) as ws:ws.receive_json()


def test_live_mode_fails_closed(tmp_path):
    with pytest.raises(RuntimeError,match='Live adapter'):
        with TestClient(create_app(config(tmp_path,data_mode='live'))):pass


def test_duplicate_signal_suppressed(tmp_path,monkeypatch):
    from app.zone_board import scan_zones as legacy_scan
    monkeypatch.setattr('app.service.scan_zones',legacy_scan)
    from test_engine import fixture_bars
    cfg=config(tmp_path)
    store=Store(cfg.database_url)
    market=Market(cfg,store)
    market.signals=[];market.bars=fixture_bars();market.now=36000
    market.check_signals();n=len(market.signals)
    assert n>0
    market.check_signals()
    assert len(market.signals)==n
    store.close()

def test_tick_advances_and_persists(tmp_path):
    import asyncio
    cfg=config(tmp_path)
    store=Store(cfg.database_url)
    market=Market(cfg,store)
    before=market.now
    asyncio.run(market.tick())
    assert market.now==before+cfg.simulation_step_seconds
    state,signals=store.load()
    assert state['now']==market.now and state['price']==market.price
    store.close()

def test_storage_failure_does_not_publish_uncommitted_state(tmp_path,monkeypatch):
    import asyncio
    cfg=config(tmp_path)
    store=Store(cfg.database_url)
    market=Market(cfg,store)
    before=market.snapshot()
    def fail(*args):raise RuntimeError('disk unavailable')
    monkeypatch.setattr(store,'save',fail)
    with pytest.raises(RuntimeError):asyncio.run(market.tick())
    assert market.snapshot()==before
    store.close()


def test_telegram_disabled_never_sends(tmp_path,monkeypatch):
    import asyncio
    import httpx
    def forbidden(*args,**kwargs):raise AssertionError('disabled notifications must not open network client')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    cfg=config(tmp_path)
    store=Store(cfg.database_url)
    market=Market(cfg,store)
    asyncio.run(market.notify({}))
    assert market.notification_status=='Disabled'
    store.close()


def test_telegram_payload_and_secret_redaction(tmp_path,monkeypatch):
    import asyncio
    import httpx
    sent=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,json):
            sent.append(json)
            return httpx.Response(200,json={'ok':True})
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    cfg=config(tmp_path,telegram_enabled=True,telegram_bot_token='test-secret',telegram_chat_id='123')
    store=Store(cfg.database_url)
    market=Market(cfg,store)
    asyncio.run(market.notify(dict(side='BUY',timeframe='M5',entry_low=2000,entry_high=2001,stop=1990,targets=[2010,2020,2030])))
    assert sent[0]['text'].startswith('SIMULATED')
    assert 'test-secret' not in str(market.snapshot())
    assert market.notification_status=='Last alert delivered'
    store.close()


def test_analysis_endpoint_matches_snapshot_and_exposes_no_credentials(tmp_path):
    cfg=config(tmp_path,telegram_bot_token='analysis-secret')
    with TestClient(create_app(cfg)) as client:
        result=client.get('/api/analysis')
        assert result.status_code==200
        assert result.json()==client.get('/api/snapshot').json()['analysis']
        assert result.json()['by_timeframe']['M1']['ready'] is False
        assert 'analysis-secret' not in result.text
        assert client.get('/api/config').json()['strategy']=='supply-demand-rr-v4'
