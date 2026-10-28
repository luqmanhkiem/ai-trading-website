"""Provider boundary: add a credentialed broker adapter here; never silently fall back."""
import random
from typing import Protocol
from .engine import Candle

class PriceProvider(Protocol):
    def next_price(self, previous: float) -> float: ...

class SimulatedProvider:
    def __init__(self, seed):
        self.random = random.Random(seed)

    def next_price(self, previous):
        return round(max(1, previous + self.random.gauss(0, 0.85)),2)

    def warmup(self, end):
        price = 2680.0  # Arbitrary synthetic starting value, not a current market quote.
        bars = []
        for t in range(end-300*240, end, 300):
            opening = price
            path = [opening]
            for _ in range(20):
                price = self.next_price(price)
                path.append(price)
            bars.append(Candle(t,opening,max(path),min(path),price))
        return bars

class BrokerProvider:
    def __init__(self, *_):
        raise RuntimeError('Live adapter is not implemented. Set DATA_MODE=simulated. Broker credentials alone do not enable live data.')
