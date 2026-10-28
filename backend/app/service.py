from .telegram import TelegramService
import asyncio
import copy
import logging
import time
import uuid
import httpx
from .engine import Candle, aggregate, evaluate, advance, metrics
from .reference_rules import invalidate_confirmed_pending as invalidate_pending
from .reference_rules import confirmed_candidates as scan_zones, STRATEGY
from .providers import SimulatedProvider, BrokerProvider

log = logging.getLogger(__name__)
class Market:
    mode = "simulated"
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        if settings.data_mode != 'simulated':
            BrokerProvider()
        self.provider = SimulatedProvider(settings.simulation_seed)
        state, self.signals = store.load()
        self.telegram = TelegramService(settings)
        self.feed_error = None
        if state:
            self.now, self.price = state['now'], state['price']
            self.bars = [Candle(**b) for b in state['bars']]
            self.current = Candle(**state['current'])
        else:
            self.now = int(time.time())//300*300
            self.bars = self.provider.warmup(self.now)
            self.price = self.bars[-1].close
            self.current = Candle(self.now,self.price,self.price,self.price,self.price)
        self.last_update = time.time()
        self.reasons = {tf:'Waiting for the next completed candle; no backfilled setups.' for tf in ('M5','M15')}
        self.persist()

    def check_signals(self):
        for tf in (5,15):
            candidates,reason=scan_zones(self.bars,tf,self.now)
            self.reasons[f'M{tf}']=reason
            recorded={s.get('zone_id') for s in self.signals}
            active=sum(s.get('strategy') in {c.get('strategy') for c in candidates} and s['timeframe']==f'M{tf}' and s['status'] in ('PENDING','OPEN') for s in self.signals)
            for candidate in candidates:
                if candidate['zone_id'] in recorded or active>=6:continue
                boundary = (getattr(self,'bid',None) if candidate['side']=='BUY' else getattr(self,'ask',None))
                if boundary is None:boundary=self.price
                if boundary is not None and (boundary-candidate['stop'])*(1 if candidate['side']=='BUY' else -1)<=0:continue
                candidate.update(id=str(uuid.uuid4()),mode=self.mode)
                self.signals.append(candidate)
                recorded.add(candidate['zone_id']);active+=1

    def persist(self):
        self.store.save(dict(now=self.now,price=self.price,bars=[b.json() for b in self.bars],current=self.current.json()),self.signals)

    @property
    def notification_status(self): return self.telegram.status

    async def notify(self, signal):
        await self.telegram.send_signal(signal,self.mode,getattr(self,'source_label',self.mode))

    async def tick(self):
        # Keep the visible state at its last committed snapshot on storage failure.
        names = ('now','price','bars','current','signals','reasons','last_update')
        checkpoint = copy.deepcopy({name:getattr(self,name) for name in names})
        try:
            await self._tick()
        except Exception:
            for name,value in checkpoint.items():
                setattr(self,name,value)
            raise

    async def _tick(self):
        self.now += self.settings.simulation_step_seconds
        self.price = self.provider.next_price(self.price)
        closed_bars = self.bars + ([self.current] if self.now//300*300 != self.current.time else [])
        invalidate_pending(closed_bars,self.now,self.signals)
        for s in self.signals:
            advance(s,self.price,self.now)
        start = self.now//300*300
        new_signals = []
        if start != self.current.time:
            self.bars.append(self.current)
            self.bars = self.bars[-600:]
            self.current = Candle(start,self.price,self.price,self.price,self.price)
            count = len(self.signals)
            self.check_signals()
            new_signals = self.signals[count:]
        else:
            self.current.high = max(self.current.high,self.price)
            self.current.low = min(self.current.low,self.price)
            self.current.close = self.price
        self.persist()
        self.last_update = time.time()
        for s in new_signals:
            await self.notify(s)

    async def run(self):
        while True:
            await asyncio.sleep(self.settings.tick_seconds)
            try:
                await self.tick()
                self.feed_error = None
            except Exception:
                self.feed_error = 'Feed paused: storage or processing failed. Check server logs.'
                log.exception('Simulation processing failed')
                return  # Fail closed instead of emitting unpersisted outcomes.

    def snapshot(self):
        bars15 = aggregate(self.bars,900,self.now)
        return dict(mode='simulated', symbol='XAUUSD', price=self.price, simulation_time=self.now,
                    updated_at=self.last_update, acceleration=self.settings.simulation_step_seconds/self.settings.tick_seconds,
                    feed_error=self.feed_error, candles=[b.json() for b in self.bars[-100:]]+[self.current.json()],
                    candles_m15=[b.json() for b in bars15[-100:]],
                    signals=list(reversed(self.signals)), metrics=metrics(self.signals), reasons=self.reasons,
                    telegram=self.telegram.snapshot(),
                    news={'configured':False,'events':[],'message':'Calendar provider not connected. No economic events have been loaded.'})
