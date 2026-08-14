from functools import lru_cache

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
    api_base_url: str = "https://openapi.tossinvest.com"


@lru_cache
def settings() -> Settings:
    return Settings()
