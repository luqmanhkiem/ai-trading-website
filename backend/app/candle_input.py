from pydantic import BaseModel, ConfigDict, Field, model_validator

class BarInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    time: int = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)

    @model_validator(mode='after')
    def validate_ohlc(self):
        if self.low > min(self.open,self.close) or self.high < max(self.open,self.close) or self.low > self.high:
            raise ValueError('Invalid OHLC range')
        if self.time % 300:
            raise ValueError('M5 candle time must align to a UTC five-minute boundary')
        return self

