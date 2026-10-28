from .telegram import TelegramService
"""Shared read-only, bid/ask paper accounting for validated provider packets."""
import asyncio
import copy
import time
import uuid
from .engine import Candle, aggregate, advance, metrics, evaluate
from .service import Market
from .reference_rules import invalidate_confirmed_pending as invalidate_pending

class QuoteMarket(Market):
    mode = 'live'
    source_label = 'Live provider'

    def __init__(self, settings, store):
        self.settings,self.store = settings,store
        self.validate_settings()
        self.telegram = TelegramService(settings)
        state,self.signals = store.load()
        self.now,self.price = 0,None
        self.bars,self.current = [],None
        self.last_update = 0  # Persisted history never implies a fresh terminal connection.
        self.last_tick_ms = 0
        self.bid,self.ask = None,None
        self.specs = None
        self.last_evaluated_bar = None
        self.feed_error = f'Waiting for {self.source_label}. No simulated fallback.'
        self.reasons = {'M5':'Waiting for live closed candles.','M15':'Waiting for live closed candles.'}
        self.lock = None
        if state:
            if state['symbol'] != self.instrument:
                raise RuntimeError('Stored instrument differs. Use a separate database for a different instrument.')
            self.bars=[Candle(**b) for b in state['bars']]
            self.current=Candle(**state['current']) if state['current'] else None
            self.price,self.now=state['price'],state['now']
            self.last_tick_ms=state['last_tick_ms']
            self.bid,self.ask=state['bid'],state['ask']
            self.specs=state.get('specs')
            self.last_evaluated_bar=state.get('last_evaluated_bar')

    def check_signals(self):
        # Zone observations start now; no historical fills/results are inferred.
        return super().check_signals()

    def stale(self):
        return self.last_update == 0 or time.time()-self.last_update > self.stale_seconds

    def persist(self):
        self.store.save(dict(symbol=self.instrument,now=self.now,price=self.price,
            bid=self.bid,ask=self.ask,last_tick_ms=self.last_tick_ms,
            bars=[b.json() for b in self.bars],current=self.current.json() if self.current else None,
            specs=self.specs,last_evaluated_bar=self.last_evaluated_bar),self.signals)

    async def ingest(self, packet):
        if self.lock is None:
            self.lock = asyncio.Lock()
        async with self.lock:
            return await self._ingest(packet)

    async def _ingest(self, packet):
        wall=time.time()
        if packet.symbol != self.instrument:
            raise ValueError('Instrument does not match the configured data source.')
        if not self.accepts_source(packet.broker):
            raise ValueError('Data source identity does not match.')
        tick_time=packet.tick_time_ms/1000
        if wall-tick_time > self.stale_seconds or tick_time-wall > 5:
            raise ValueError('Stale/future quote rejected. Check source timestamps and server clock.')
        if packet.tick_time_ms <= self.last_tick_ms:
            return {'accepted':False,'reason':'Duplicate or out-of-order quote ignored'}
        current_start=int(tick_time)//300*300
        if packet.bars[-1].time != current_start:
            raise ValueError('Current candle is missing or ahead of the quote timestamp.')
        complete=[Candle(**b.model_dump()) for b in packet.bars[:-1]]
        names=('now','price','bars','current','signals','last_update','last_tick_ms','bid','ask','specs','last_evaluated_bar','reasons','feed_error')
        checkpoint=copy.deepcopy({n:getattr(self,n) for n in names})
        count=len(self.signals)
        try:
            was_stale=self.stale()
            # A loss of quote coverage invalidates active paper trades. Never invent missed fills.
            if was_stale:
                for s in self.signals:
                    if s['status'] in ('OPEN','PENDING'):
                        s.update(status='DATA_GAP',closed_at=int(tick_time),result_r=None,
                                 invalidation_reason='Quote coverage interrupted; outcome unknown.')
            self.now=int(tick_time)
            self.price=self.bid=packet.bid
            self.ask=packet.ask
            if not was_stale:
                invalidate_pending(complete,self.now,self.signals)
                for s in self.signals:
                    # Buy entry uses ask, sell entry uses bid; exits use the opposite side.
                    price=(packet.ask if s['side']=='BUY' else packet.bid) if s['status']=='PENDING' else (packet.bid if s['side']=='BUY' else packet.ask)
                    advance(s,price,self.now,boundary_price=packet.bid if s['side']=='BUY' else packet.ask)
            self.bars=complete[-600:]
            self.current=Candle(**packet.bars[-1].model_dump())
            self.specs=dict(contract_size=packet.contract_size,lot_step=packet.lot_step,min_lot=packet.min_lot,max_lot=packet.max_lot) if packet.contract_size is not None else None
            latest=self.bars[-1].time
            if self.last_evaluated_bar is not None and latest > self.last_evaluated_bar and not was_stale:
                self.check_signals()
            elif was_stale or self.last_evaluated_bar is None:
                self.check_signals()
            self.last_evaluated_bar=latest
            self.last_tick_ms=packet.tick_time_ms
            self.last_update=wall
            self.feed_error=None
            self.persist()
        except Exception:
            for n,v in checkpoint.items():setattr(self,n,v)
            raise
        for s in self.signals[count:]:
            await self.notify(s)
        return {'accepted':True,'mode':self.mode,'paper_only':True}

    async def run(self):
        # Push-based providers wait here; polling providers override this method.
        while True:
            await asyncio.sleep(1)

    def snapshot(self):
        gap_count=sum(s['status']=='DATA_GAP' for s in self.signals)
        return dict(mode=self.mode,symbol=self.instrument,price=self.price,simulation_time=self.now,
            updated_at=self.last_update,acceleration=1,feed_error=self.feed_error or (f'{self.source_label} quote stale. Paper evaluation paused.' if self.stale() else None),
            source=self.source_label,bid=self.bid,ask=self.ask,broker_specs=self.specs,
            candles=[b.json() for b in self.bars[-100:]]+([self.current.json()] if self.current else []),
            candles_m15=[b.json() for b in aggregate(self.bars,900,self.now)[-100:]],signals=list(reversed(self.signals)),
            metrics={**metrics(self.signals),'data_gaps':gap_count},reasons=self.reasons,
            telegram=self.telegram.snapshot(),
            news={'configured':False,'events':[],'message':'Calendar provider not connected. No economic events have been loaded.'})
