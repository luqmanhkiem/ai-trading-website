"""Read-only MT5 push ingestion. No terminal login and no order execution."""
import asyncio
import copy
import time
import uuid
from typing import List
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .engine import Candle, aggregate, advance, metrics, evaluate
from .service import Market

from .candle_input import BarInput

class BridgeInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    symbol: str = Field(min_length=1,max_length=40,pattern=r'^[A-Za-z0-9._-]+$')
    broker: str = Field(min_length=1,max_length=100)
    tick_time_ms: int = Field(gt=0)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    server_utc_offset_seconds: int = Field(ge=-50400,le=50400)
    contract_size: float = Field(gt=0)
    lot_step: float = Field(gt=0)
    min_lot: float = Field(gt=0)
    max_lot: float = Field(gt=0)
    # 240 completed M5 bars + current bar from terminal. Gaps are retained, never filled.
    bars: List[BarInput] = Field(min_length=91,max_length=601)

    @model_validator(mode='after')
    def validate_payload(self):
        if self.ask < self.bid or self.min_lot > self.max_lot:
            raise ValueError('Invalid spread or volume limits')
        if self.server_utc_offset_seconds % 300:
            raise ValueError('Server offset must preserve UTC M5 alignment')
        times = [b.time for b in self.bars]
        if times != sorted(set(times)):
            raise ValueError('Candles must be strictly increasing with no duplicate timestamps')
        return self

from .quote_market import QuoteMarket

class MT5Market(QuoteMarket):
    mode = 'mt5'
    source_label = 'Valetax MT5'

    @property
    def instrument(self): return self.settings.mt5_symbol

    @property
    def stale_seconds(self): return self.settings.mt5_stale_seconds

    def accepts_source(self, broker): return 'valetax' in broker.lower()

    def validate_settings(self):
        if len(self.settings.mt5_bridge_token) < 32:
            raise RuntimeError('MT5_BRIDGE_TOKEN must contain at least 32 characters; generate it locally.')
        if not self.instrument.upper().startswith('XAUUSD'):
            raise RuntimeError('MT5_SYMBOL must be your exact Valetax XAUUSD symbol, including its suffix.')
