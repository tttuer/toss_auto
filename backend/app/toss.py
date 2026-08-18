import asyncio
import logging
import random
import time
from datetime import date
from decimal import Decimal

import httpx

from app.config import Settings


logger = logging.getLogger(__name__)


class RateLimitExceeded(RuntimeError):
    """토스가 안내한 대기 시간만큼 재시도한 뒤에도 호출 한도를 넘긴 경우."""


class TossClient:
    def __init__(self, config: Settings):
        self.config, self.token, self.account_seq = config, None, config.toss_account_seq
        self._market_calendars: dict[tuple[str, date], dict] = {}
        self._next_market_info_request_at = 0.0

    async def _token(self) -> str:
        if self.token:
            return self.token
        async with httpx.AsyncClient(base_url=self.config.api_base_url, timeout=15) as client:
            response = await client.post("/oauth2/token", data={"grant_type": "client_credentials", "client_id": self.config.toss_client_id, "client_secret": self.config.toss_client_secret})
            response.raise_for_status()
            self.token = response.json()["access_token"]
            return self.token

    async def _get(self, path: str, account: bool = True, **params: str) -> dict:
        token = await self._token()
        headers = {"Authorization": f"Bearer {token}"}
        if account:
            headers["X-Tossinvest-Account"] = await self._account_seq()
        for attempt in range(4):
            async with httpx.AsyncClient(base_url=self.config.api_base_url, timeout=15) as client:
                response = await client.get(path, params=params, headers=headers)
            if response.status_code != 429:
                if response.is_error:
                    logger.warning("토스 API 요청 실패: %s %s", path, response.text[:500])
                response.raise_for_status()
                return response.json()["result"]
            if attempt == 3:
                raise RateLimitExceeded(f"토스 호출 한도 초과: {path}")
            await asyncio.sleep(self._retry_delay(response, attempt))

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        try:
            return max(float(response.headers["Retry-After"]), 0.4) + random.uniform(0, 0.2)
        except (KeyError, ValueError):
            return 2**attempt + random.uniform(0, 0.2)

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            error = response.json().get("error", {})
            return ": ".join(part for part in (error.get("code"), error.get("message")) if part)
        except (ValueError, AttributeError):
            return response.text[:500]

    async def accounts(self) -> list[dict]:
        return await self._get("/api/v1/accounts", account=False)

    async def _account_seq(self) -> str:
        if self.account_seq:
            return self.account_seq
        accounts = await self.accounts()
        if len(accounts) != 1:
            raise RuntimeError("자동매매 계좌가 하나여야 합니다. TOSS_ACCOUNT_SEQ를 직접 설정해 주세요.")
        self.account_seq = str(accounts[0]["accountSeq"])
        return self.account_seq

    async def buying_power(self, currency: str) -> Decimal:
        return Decimal((await self._get("/api/v1/buying-power", currency=currency))["cashBuyingPower"])

    async def prices(self, symbols: list[str]) -> dict[str, Decimal]:
        try:
            return await self._prices(symbols)
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 400 or len(symbols) == 1:
                raise
            logger.warning("현재가 묶음 조회가 거절되어 종목별 조회로 전환합니다.")
            prices: dict[str, Decimal] = {}
            for symbol in symbols:
                try:
                    prices.update(await self._prices([symbol]))
                except httpx.HTTPStatusError:
                    logger.exception("현재가 조회 실패: %s", symbol)
            if prices:
                return prices
            raise error

    async def _prices(self, symbols: list[str]) -> dict[str, Decimal]:
        return {item["symbol"]: Decimal(item["lastPrice"]) for item in await self._get("/api/v1/prices", symbols=",".join(symbols))}

    async def market_calendar(self, market: str, target: date) -> dict:
        key = (market, target)
        if key not in self._market_calendars:
            delay = self._next_market_info_request_at - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_market_info_request_at = time.monotonic() + 0.4
            self._market_calendars[key] = await self._get(f"/api/v1/market-calendar/{market}", date=target.isoformat())
        return self._market_calendars[key]

    async def is_open(self, market: str, target: date) -> bool:
        result = await self.market_calendar(market, target)
        return bool(result["today"].get("integrated") or result["today"].get("regularMarket"))

    async def create_order(self, payload: dict) -> str:
        token = await self._token()
        headers = {"Authorization": f"Bearer {token}", "X-Tossinvest-Account": await self._account_seq()}
        async with httpx.AsyncClient(base_url=self.config.api_base_url, timeout=15) as client:
            response = await client.post("/api/v1/orders", json=payload, headers=headers)
            if response.is_error:
                message = self._error_message(response)
                logger.warning("주문 요청 실패: %s", message)
                raise RuntimeError(f"주문 요청 실패 ({response.status_code}): {message}")
            return response.json()["result"]["orderId"]
