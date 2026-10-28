"""Direct OANDA v20 REST polling. GET requests only; no order API."""
import asyncio
import time
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from urllib.parse import quote
import httpx
from .candle_input import BarInput
from .quote_market import QuoteMarket

class FeedError(Exception):
    """Safe user-facing text, never a raw authenticated URL or response body."""

def timestamp(value):
    # OANDA Accept-Datetime-Format: UNIX returns fractional epoch seconds.
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number <= 0: raise ValueError()
        return number
    except (ValueError,InvalidOperation):
        raise FeedError('Invalid OANDA timestamp.') from None

class OandaClient:
    def __init__(self, settings, client=None):
        host={'practice':'https://api-fxpractice.oanda.com','live':'https://api-fxtrade.oanda.com'}[settings.oanda_environment]
        self.settings=settings
        self.client=client or httpx.AsyncClient(base_url=host,headers={
            'Authorization':'Bearer '+settings.oanda_api_token,
            'Accept-Datetime-Format':'UNIX'},timeout=8,follow_redirects=False)
        self.account=quote(settings.oanda_account_id,safe='')
        self.instrument=quote(settings.oanda_instrument,safe='')

    async def get(self,path,params=None):
        try:
            response=await self.client.get(path,params=params)
        except httpx.RequestError:
            raise FeedError('OANDA network error. Retrying with backoff; evaluation paused.') from None
        if response.status_code in (401,403):
            raise FeedError('OANDA access denied. Check API token, account ID and practice/live environment.')
        if response.status_code==429:
            raise FeedError('OANDA rate limit reached. Retrying with backoff.')
        if response.status_code!=200:
            raise FeedError(f'OANDA returned HTTP {response.status_code}. Check account access and instrument availability.')
        try:return response.json()
        except ValueError:raise FeedError('Invalid OANDA JSON response.') from None

    async def verify_instrument(self):
        data=await self.get(f'/v3/accounts/{self.account}/instruments',{'instruments':self.settings.oanda_instrument})
        if not any(i.get('name')==self.settings.oanda_instrument for i in data.get('instruments',[])):
            raise FeedError('XAU_USD is not available to this OANDA account. No alternative feed is substituted.')

    async def candles(self):
        data=await self.get(f'/v3/accounts/{self.account}/instruments/{self.instrument}/candles',
            {'granularity':'M5','price':'B','count':241,'smooth':'false'})
        if data.get('instrument')!=self.settings.oanda_instrument or data.get('granularity')!='M5':
            raise FeedError('OANDA candle identity or timeframe mismatch.')
        result=[]
        try:
            for c in data['candles']:
                raw_time=timestamp(c['time'])
                if raw_time != int(raw_time):raise ValueError()
                b=c['bid']
                bar=BarInput(time=int(raw_time),open=b['o'],high=b['h'],low=b['l'],close=b['c'])
                if not isinstance(c['complete'],bool):raise ValueError()
                result.append((bar,c['complete']))
            times=[b.time for b,_ in result]
            if len(times)<91 or times!=sorted(set(times)):raise ValueError()
        except (KeyError,TypeError,ValueError):
            raise FeedError('Invalid or insufficient OANDA candle history.') from None
        return result

    async def pricing(self):
        data=await self.get(f'/v3/accounts/{self.account}/pricing',{'instruments':self.settings.oanda_instrument})
        try:
            prices=[p for p in data['prices'] if p['instrument']==self.settings.oanda_instrument]
            if len(prices)!=1:raise ValueError()
            p=prices[0]
            if p.get('status')!='tradeable' or p.get('tradeable') is False:
                raise FeedError('OANDA market is not tradeable. Quote evaluation paused.')
            bid,ask=float(p['bids'][0]['price']),float(p['asks'][0]['price'])
            if not (0<bid<=ask<float('inf')):raise ValueError()
            return int(timestamp(p['time'])*1000),bid,ask
        except (KeyError,TypeError,ValueError,IndexError):
            raise FeedError('Invalid OANDA pricing response.') from None

    async def close(self):await self.client.aclose()

class OandaMarket(QuoteMarket):
    mode='oanda'

    @property
    def source_label(self):return f'OANDA {self.settings.oanda_environment}'
    @property
    def instrument(self):return self.settings.oanda_instrument
    @property
    def stale_seconds(self):return self.settings.oanda_stale_seconds
    def accepts_source(self,source):return source==self.source_label
    def validate_settings(self):
        if self.settings.oanda_environment not in ('practice','live'):
            raise RuntimeError('OANDA_ENVIRONMENT must be practice or live.')
        if self.instrument!='XAU_USD':raise RuntimeError('This gold MVP requires OANDA_INSTRUMENT=XAU_USD.')

    def __init__(self,settings,store):
        super().__init__(settings,store)
        self.feed_error='OANDA credentials missing. Add OANDA_API_TOKEN and OANDA_ACCOUNT_ID on the server.' if not self.configured else 'Connecting directly to OANDA…'
        self.cached_candles=None
        self.candles_fetched_at=0

    @property
    def configured(self):return bool(self.settings.oanda_api_token and self.settings.oanda_account_id)

    async def poll(self,provider):
        # Candle closure is confirmed by OANDA's complete flag, not inferred from wall time.
        if self.cached_candles is None or self.candles_fetched_at==0 or time.monotonic()-self.candles_fetched_at>=10:
            self.cached_candles=await provider.candles()
            self.candles_fetched_at=time.monotonic()
        tick_ms,bid,ask=await provider.pricing()
        start=tick_ms//300000*300
        complete=[b for b,done in self.cached_candles if done and b.time+300<=start]
        partial=[b for b,done in self.cached_candles if not done and b.time==start]
        if len(complete)<90 or not partial or complete[-1].time!=start-300:
            # A boundary may arrive before the candle endpoint confirms closure. Do not guess.
            self.candles_fetched_at=0
            raise FeedError('Waiting for OANDA to confirm the latest closed M5 candle.')
        if self.current and self.current.time==start:
            # Keep bid candle shape current between historical-candle refreshes.
            old=self.current
            base=partial[0]
            current=BarInput(time=start,open=base.open,high=max(base.high,old.high,bid),low=min(base.low,old.low,bid),close=bid)
        else:
            b=partial[0]
            current=BarInput(time=start,open=b.open,high=max(b.high,bid),low=min(b.low,bid),close=bid)
        packet=SimpleNamespace(symbol=self.instrument,broker=self.source_label,tick_time_ms=tick_ms,bid=bid,ask=ask,
            bars=complete+[current],contract_size=None,lot_step=None,min_lot=None,max_lot=None)
        result=await self.ingest(packet)
        if not result['accepted'] and self.stale():
            raise FeedError('OANDA quote unchanged or stale. Paper evaluation paused.')
        self.feed_error=None

    async def run(self):
        if not self.configured:
            while True:await asyncio.sleep(60)
        provider=OandaClient(self.settings)
        backoff=self.settings.oanda_poll_seconds
        verified=False
        try:
            while True:
                try:
                    if not verified:
                        await provider.verify_instrument();verified=True
                    await self.poll(provider)
                    backoff=self.settings.oanda_poll_seconds
                except (FeedError,ValueError) as e:
                    self.feed_error=str(e) if isinstance(e,FeedError) else 'OANDA packet validation failed. Evaluation paused.'
                    backoff=min(max(backoff*2,2),60)
                except Exception:
                    # Raw HTTP errors may contain account IDs. Never surface or log them.
                    self.feed_error='OANDA processing or storage error. Evaluation paused; retrying.'
                    backoff=min(max(backoff*2,2),60)
                await asyncio.sleep(backoff)
        finally:await provider.close()
