import asyncio
import copy
import time
import pytest
import httpx
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.oanda import OandaClient,OandaMarket,FeedError,timestamp
from app.storage import Store
from test_mt5 import BASE,payload

def settings(tmp_path,**changes):
    return Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/oanda.db',data_mode='oanda',**changes)

def provider(cfg,handler):
    client=httpx.AsyncClient(base_url='https://api-fxpractice.oanda.com',headers={'Authorization':'Bearer test-only-secret'},transport=httpx.MockTransport(handler))
    return OandaClient(cfg,client)

def candles(now=BASE+299):
    packet=payload(now)
    return dict(instrument='XAU_USD',granularity='M5',candles=[dict(time=str(b['time']),complete=i<len(packet['bars'])-1,bid=dict(o=str(b['open']),h=str(b['high']),l=str(b['low']),c=str(b['close']))) for i,b in enumerate(packet['bars'])])

def pricing(now=BASE+299,status='tradeable'):
    return dict(prices=[dict(instrument='XAU_USD',time=str(now),status=status,bids=[{'price':'2120.2'}],asks=[{'price':'2120.3'}])])

def test_no_credentials_gives_empty_feed_not_simulation(tmp_path):
    cfg=settings(tmp_path)
    with TestClient(create_app(cfg)) as client:
        snap=client.get('/api/snapshot').json()
        assert snap['mode']=='oanda' and snap['price'] is None and snap['candles']==[]
        assert 'credentials missing' in snap['feed_error']
        assert snap['metrics']['closed']==0
        assert client.post('/api/mt5/ingest',json={}).status_code==409

def test_readonly_requests_and_complete_candle_mapping(tmp_path):
    cfg=settings(tmp_path,oanda_api_token='test-only-secret',oanda_account_id='test-account')
    requests=[]
    def handler(request):
        requests.append(request)
        if request.url.path.endswith('/instruments'):data={'instruments':[{'name':'XAU_USD'}]}
        elif request.url.path.endswith('/candles'):data=candles()
        else:data=pricing()
        return httpx.Response(200,json=data)
    async def run():
        p=provider(cfg,handler)
        await p.verify_instrument()
        bars=await p.candles()
        quote=await p.pricing()
        await p.close()
        return bars,quote
    bars,q=asyncio.run(run())
    assert len(bars)==121 and bars[-1][1] is False and bars[-2][1] is True
    assert q==((BASE+299)*1000,2120.2,2120.3)
    assert all(r.method=='GET' for r in requests)
    assert all('test-only-secret' not in str(r.url) for r in requests)
    assert requests[1].url.params['price']=='B'

@pytest.mark.parametrize('status',[401,403,404,429,503])
def test_errors_redact_provider_body_and_credentials(tmp_path,status):
    cfg=settings(tmp_path)
    async def run():
        p=provider(cfg,lambda r:httpx.Response(status,json={'errorMessage':'private-token-and-account'}))
        try:await p.verify_instrument()
        finally:await p.close()
    with pytest.raises(FeedError) as e:asyncio.run(run())
    assert 'private-token-and-account' not in str(e.value)

def test_instrument_must_be_available(tmp_path):
    async def run():
        p=provider(settings(tmp_path),lambda r:httpx.Response(200,json={'instruments':[{'name':'EUR_USD'}]}))
        try:await p.verify_instrument()
        finally:await p.close()
    with pytest.raises(FeedError,match='not available'):asyncio.run(run())

def test_closed_market_pauses(tmp_path):
    async def run():
        p=provider(settings(tmp_path),lambda r:httpx.Response(200,json=pricing(status='non-tradeable')))
        try:await p.pricing()
        finally:await p.close()
    with pytest.raises(FeedError,match='not tradeable'):asyncio.run(run())

def test_fractional_unix_time_and_invalid_prices(tmp_path):
    assert int(timestamp('1800000299.123456789')*1000)==1800000299123
    for bad in ('NaN','Infinity','broken',-2):
        with pytest.raises(FeedError):timestamp(bad)
    doc=pricing();doc['prices'][0]['asks'][0]['price']='nan'
    async def run():
        p=provider(settings(tmp_path),lambda r:httpx.Response(200,json=doc))
        try:await p.pricing()
        finally:await p.close()
    with pytest.raises(FeedError):asyncio.run(run())

def test_oanda_bootstrap_no_backfill_and_new_candle_signal(tmp_path,monkeypatch):
    monkeypatch.setattr('app.oanda.time.time',lambda:BASE+299)
    cfg=settings(tmp_path)
    store=Store(cfg.database_url,'oanda:practice')
    market=OandaMarket(cfg,store)
    now=[BASE+299]
    class Source:
        async def candles(self):
            doc=candles()
            if now[0]>=BASE+300:
                doc['candles'][-1]['complete']=True
                doc['candles'].append(dict(time=str(BASE+300),complete=False,bid=dict(o='2120.2',h='2120.4',l='2120.1',c='2120.2')))
            from app.mt5 import BarInput
            return [(BarInput(time=int(c['time']),open=c['bid']['o'],high=c['bid']['h'],low=c['bid']['l'],close=c['bid']['c']),c['complete']) for c in doc['candles']]
        async def pricing(self):return now[0]*1000,2120.2,2120.3
    asyncio.run(market.poll(Source()))
    assert market.signals==[] and market.snapshot()['source']=='OANDA practice'
    now[0]=BASE+300;monkeypatch.setattr('app.oanda.time.time',lambda:BASE+300)
    market.candles_fetched_at=0
    asyncio.run(market.poll(Source()))
    assert market.signals==[]  # A monotonic move without a consolidation zone must not force a setup.
    assert market.last_evaluated_bar==BASE
    assert market.snapshot()['broker_specs'] is None  # Do not import OANDA units into Valetax lot sizing.
    store.close()

def test_practice_live_mt5_and_simulation_are_isolated(tmp_path):
    cfg=settings(tmp_path)
    practice=Store(cfg.database_url,'oanda:practice')
    practice.save({'symbol':'XAU_USD'},[dict(id='record',created_at=1)])
    for mode in ('oanda:live','mt5','simulated'):
        other=Store(cfg.database_url,mode)
        assert other.load()==(None,[])
        other.close()
    assert practice.load()[1][0]['id']=='record'
    practice.close()

def test_config_does_not_expose_token_or_account(tmp_path):
    cfg=settings(tmp_path,oanda_api_token='secret-private-key',oanda_account_id='private-account-123')
    # Avoid external network in startup: patch run instead of calling a provider.
    async def parked(self):await asyncio.sleep(60)
    from unittest.mock import patch
    with patch.object(OandaMarket,'run',parked):
        with TestClient(create_app(cfg)) as client:
            text=client.get('/api/config').text+client.get('/api/snapshot').text
            assert 'secret-private-key' not in text and 'private-account-123' not in text

def test_unconfirmed_closed_bar_does_not_generate_signals(tmp_path,monkeypatch):
    from app.candle_input import BarInput
    monkeypatch.setattr('app.oanda.time.time',lambda:BASE+299)
    cfg=settings(tmp_path)
    store=Store(cfg.database_url,'oanda:practice')
    market=OandaMarket(cfg,store)
    class Source:
        async def candles(self):
            doc=candles();doc['candles'][-2]['complete']=False
            return [(BarInput(time=int(c['time']),open=c['bid']['o'],high=c['bid']['h'],low=c['bid']['l'],close=c['bid']['c']),c['complete']) for c in doc['candles']]
        async def pricing(self):return (BASE+299)*1000,2120.2,2120.3
    with pytest.raises(FeedError,match='confirm'):asyncio.run(market.poll(Source()))
    assert market.price is None and market.signals==[] and market.candles_fetched_at==0
    store.close()
