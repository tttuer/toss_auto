from functools import lru_cache
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./toss_auto.db"
    toss_client_id: str = ""
    toss_client_secret: str = ""
    toss_account_seq: str = ""
    live_trading: bool = True
    auto_run_enabled: bool = True
    investment_day: int = 16
    monthly_krw_budget: Decimal = Decimal("1350000")
    monthly_us_krw_budget: Decimal = Decimal("7650000")
    api_base_url: str = "https://openapi.tossinvest.com"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


@lru_cache
def settings() -> Settings:
    return Settings()
