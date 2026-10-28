from .pressure import pressure_snapshot
from .market_analysis import AnalysisService
import asyncio
import secrets
import hashlib
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from .config import Settings
from .engine import lot_size
from .storage import Store
from .service import Market
from .mt5 import MT5Market, BridgeInput
from .oanda import OandaMarket
from .calendar import CalendarService
from .telegram import TelegramError

class LotRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    balance: float = Field(gt=0)
    risk_percent: float = Field(gt=0,le=100)
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    contract_size: float = Field(default=100,gt=0)
    lot_step: float = Field(default=0.01,gt=0)
    min_lot: float = Field(default=0.01,gt=0)
    max_lot: float = Field(default=100,gt=0)

def create_app(settings=None):
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        store = Store(settings.database_url,'oanda:'+settings.oanda_environment+':'+hashlib.sha256(settings.oanda_account_id.encode()).hexdigest()[:16] if settings.data_mode=='oanda' else settings.data_mode)
        try:
            market_class={"mt5":MT5Market,"oanda":OandaMarket}.get(settings.data_mode,Market)
            app.state.market = market_class(settings,store)
            app.state.calendar = CalendarService(settings,store)
            task = asyncio.create_task(app.state.market.run())
            calendar_task = asyncio.create_task(app.state.calendar.run())
            try:
                yield
            finally:
                task.cancel()
                calendar_task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                with suppress(asyncio.CancelledError):
                    await calendar_task
        finally:
            store.close()
    app = FastAPI(title='Aurum Paper Signal API',version='0.1.0',lifespan=lifespan)
    origins = settings.allowed_origins.split(',')
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

    analysis_service=AnalysisService()

    def dashboard_snapshot():
        snapshot=app.state.market.snapshot()
        snapshot['news']=app.state.calendar.snapshot()
        snapshot['analysis']=analysis_service.snapshot(app.state.market.bars,app.state.market.now)
        import time
        fresh = not snapshot.get('feed_error') and time.time()-snapshot.get('updated_at',0)<=10
        snapshot['pressure']=pressure_snapshot(app.state.market.bars,app.state.market.now,fresh)
        return snapshot

    def require_local_origin(request):
        # Side effects only from the same trusted dashboard origin; no wildcard CORS.
        if request.headers.get('origin') not in origins:
            raise HTTPException(status_code=403,detail='Use the trusted Aurum dashboard for this action.')

    @app.post('/api/telegram/test')
    async def telegram_test(request: Request):
        require_local_origin(request)
        try:
            delivered=await app.state.market.telegram.test_message(getattr(app.state.market,'source_label',settings.data_mode))
            return {'delivered':delivered,'status':app.state.market.telegram.status}
        except TelegramError as e:
            raise HTTPException(status_code=400,detail=str(e))

    @app.post('/api/news/refresh')
    async def refresh_calendar(request: Request):
        require_local_origin(request)
        await app.state.calendar.refresh()
        return app.state.calendar.snapshot()

    @app.get('/api/health')
    def health():
        return {'status':'degraded' if app.state.market.snapshot()['feed_error'] else 'ok','mode':settings.data_mode}

    @app.get('/api/snapshot')
    def snapshot():
        return dashboard_snapshot()

    @app.get('/api/analysis')
    def analysis():
        return analysis_service.snapshot(app.state.market.bars,app.state.market.now)

    @app.get('/api/signals')
    def signals():
        return app.state.market.snapshot()['signals']

    @app.get('/api/metrics')
    def performance():
        return app.state.market.snapshot()['metrics']

    @app.get('/api/news')
    def news():
        return app.state.calendar.snapshot()

    @app.get('/api/config')
    def config():
        return {'strategy':'supply-demand-rr-v4','mode':settings.data_mode,'live_adapter_implemented':True,'oanda_configured':bool(settings.oanda_api_token and settings.oanda_account_id),'oanda_environment':settings.oanda_environment,'telegram':app.state.market.snapshot()['telegram']}

    @app.post('/api/mt5/ingest')
    async def ingest(request: Request, authorization: str = Header(default='')):
        if settings.data_mode != 'mt5':
            raise HTTPException(status_code=409,detail='MT5 ingestion requires DATA_MODE=mt5. Simulation stays isolated.')
        expected = 'Bearer '+settings.mt5_bridge_token
        if not secrets.compare_digest(authorization.encode(),expected.encode()):
            raise HTTPException(status_code=401,detail='Invalid bridge token')
        # Bound the body before parsing. Tokens are never carried in URLs or responses.
        chunks=[]
        size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size > 200000:
                raise HTTPException(status_code=413,detail='Bridge payload too large')
            chunks.append(chunk)
        try:
            packet=BridgeInput.model_validate_json(b''.join(chunks))
            return await app.state.market.ingest(packet)
        except ValueError as e:
            # Validation errors must not echo the supplied document or authentication header.
            raise HTTPException(status_code=422,detail='Invalid MT5 packet: '+str(e).split('\n')[0])

    @app.post('/api/calculate-lot')
    def calculate(request: LotRequest):
        try:
            return lot_size(**request.model_dump())
        except ValueError as e:
            raise HTTPException(status_code=422,detail=str(e))

    @app.websocket('/api/ws')
    async def socket(ws: WebSocket):
        if ws.headers.get('origin') not in origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while True:
                await ws.send_json(dashboard_snapshot())
                await asyncio.sleep(settings.tick_seconds)
        except (WebSocketDisconnect,RuntimeError):
            pass
    return app

app = create_app()
