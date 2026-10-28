from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./aurum.db'
    data_mode: str = 'simulated'
    tick_seconds: float = Field(1.0, ge=0.1, le=60)
    simulation_step_seconds: int = Field(15, ge=1, le=300)
    simulation_seed: int = 42
    allowed_origins: str = 'http://127.0.0.1:5173,http://localhost:5173'
    telegram_enabled: bool = False
    telegram_bot_token: str = ''
    telegram_chat_id: str = ''
    broker_api_key: str = ''
    mt5_bridge_token: str = ''
    mt5_symbol: str = 'XAUUSD.vx'
    mt5_stale_seconds: int = Field(15,ge=5,le=120)
    oanda_environment: str = 'practice'
    oanda_api_token: str = ''
    oanda_account_id: str = ''
    oanda_instrument: str = 'XAU_USD'
    oanda_poll_seconds: float = Field(2,ge=1,le=10)
    oanda_stale_seconds: int = Field(15,ge=5,le=120)
    calendar_provider: str = 'none'
    calendar_refresh_seconds: int = Field(3600,ge=900,le=86400)
