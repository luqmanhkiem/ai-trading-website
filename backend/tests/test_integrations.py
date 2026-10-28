import asyncio
import copy
from datetime import datetime,timezone,timedelta
import importlib.util
from pathlib import Path
import pytest
import httpx
from fastapi.testclient import TestClient
from app.calendar import CalendarService,CalendarError,parse_events
from app.config import Settings
from app.storage import Store
from app.telegram import TelegramService,TelegramError,call_bot
from app.main import create_app


def cfg(tmp_path,**kwargs):
    return Settings(_env_file=None,database_url=f'sqlite:///{tmp_path}/integrations.db',**kwargs)


def events():
    d=datetime.now(timezone.utc)+timedelta(hours=2)
    return [dict(title='Test release',country='USD',date=d.isoformat(),impact='High',forecast='2.0%',previous='1.5%')]


def test_calendar_timezones_missing_values_and_deduplication():
    p=events();p[0]['date']='2026-10-16T08:30:00-04:00'
    result=parse_events(p+p)
    assert len(result)==1 and result[0]['time']==int(datetime(2026,10,16,12,30,tzinfo=timezone.utc).timestamp())
    assert result[0]['actual'] is None and result[0]['forecast']=='2.0%'
    p[0]['impact']='Holiday'
    assert parse_events(p)[0]['time_precision']=='date'

@pytest.mark.parametrize('change',[{'date':'2026-10-16T08:30:00'},{'date':'broken'},{'impact':'Imagined'},{'title':''},{'country':'XYZ'}])
def test_calendar_invalid_document_is_not_partially_accepted(change):
    p=events();p.append({**p[0],**change})
    with pytest.raises(CalendarError):parse_events(p)


def test_calendar_cache_persistence_and_throttling(tmp_path,monkeypatch):
    c=cfg(tmp_path,calendar_provider='forex_factory')
    store=Store(c.database_url)
    requests=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,headers):
            requests.append(url)
            return httpx.Response(200,json=events())
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    service=CalendarService(c,store)
    asyncio.run(service.refresh());asyncio.run(service.refresh())
    assert len(requests)==1 and len(service.snapshot()['events'])==1
    assert service.snapshot()['stale'] is False
    restored=CalendarService(c,store)
    assert restored.events==service.events
    store.close()


def test_failed_refresh_retains_data_and_marks_stale(tmp_path,monkeypatch):
    c=cfg(tmp_path,calendar_provider='forex_factory')
    store=Store(c.database_url)
    store.save_cache('calendar:forex_factory',dict(events=parse_events(events()),updated_at=1))
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,*args,**kwargs):return httpx.Response(429)
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    service=CalendarService(c,store)
    asyncio.run(service.refresh())
    assert len(service.events)==1 and service.snapshot()['stale'] is True
    assert '429' in service.snapshot()['message']
    store.close()


def test_telegram_test_disabled_never_connects(tmp_path):
    service=TelegramService(cfg(tmp_path))
    with pytest.raises(TelegramError,match='not enabled'):asyncio.run(service.test_message('Valetax MT5'))


def test_telegram_test_destination_and_cooldown(tmp_path,monkeypatch):
    requests=[]
    async def fake(token,method,payload):requests.append((token,method,payload));return {'message_id':1}
    monkeypatch.setattr('app.telegram.call_bot',fake)
    service=TelegramService(cfg(tmp_path,telegram_enabled=True,telegram_bot_token='private-secret',telegram_chat_id='destination-123'))
    assert asyncio.run(service.test_message('Valetax MT5')) is True
    assert requests[0][2]['chat_id']=='destination-123'
    assert 'No trade was placed' in requests[0][2]['text']
    assert 'private-secret' not in str(service.snapshot()) and 'destination-123' not in str(service.snapshot())
    with pytest.raises(TelegramError,match='15 seconds'):asyncio.run(service.test_message('Valetax MT5'))
    assert len(requests)==1

@pytest.mark.parametrize('status',[401,403,429,500])
def test_telegram_provider_errors_are_redacted(monkeypatch,status):
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):return httpx.Response(status,json={'ok':False,'description':'secret token body'})
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    with pytest.raises(TelegramError) as e:asyncio.run(call_bot('secret-token','getMe'))
    assert 'secret-token' not in str(e.value) and 'secret token body' not in str(e.value)


def test_side_effects_require_dashboard_origin(tmp_path):
    with TestClient(create_app(cfg(tmp_path))) as client:
        assert client.post('/api/telegram/test').status_code==403
        assert client.post('/api/telegram/test',headers={'origin':'https://evil.invalid'}).status_code==403
        assert client.post('/api/telegram/test',headers={'origin':'http://localhost:5173'}).status_code==400
        assert client.post('/api/news/refresh',headers={'origin':'http://localhost:5173'}).status_code==200
        news=client.get('/api/news').json()
        assert news['configured'] is False and news['events']==[]
        assert client.get('/api/snapshot').json()['news']==news


def test_private_setup_writer_preserves_existing_feed_and_hides_secrets(tmp_path,monkeypatch):
    source=Path(__file__).resolve().parents[2]/'scripts/setup_telegram.py'
    spec=importlib.util.spec_from_file_location('setup_telegram',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=tmp_path
    (tmp_path/'backend').mkdir()
    path=tmp_path/'backend/.env'
    path.write_text('DATA_MODE=mt5\nMT5_SYMBOL=XAUUSD.vxx\n')
    module.save_settings({'TELEGRAM_BOT_TOKEN':'123:private-key','TELEGRAM_CHAT_ID':'-1001','TELEGRAM_ENABLED':'true'})
    config=Settings(_env_file=path)
    assert config.data_mode=='mt5' and config.mt5_symbol=='XAUUSD.vxx'
    assert config.telegram_bot_token=='123:private-key' and config.telegram_enabled
    assert path.stat().st_mode&0o777==0o600
