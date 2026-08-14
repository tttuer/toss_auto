from datetime import date
from decimal import Decimal

import httpx

from app.config import Settings


class TossClient:
    def __init__(self, config: Settings):
        self.config, self.token, self.account_seq = config, None, config.toss_account_seq

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
        async with httpx.AsyncClient(base_url=self.config.api_base_url, timeout=15) as client:
            response = await client.get(path, params=params, headers=headers)
            response.raise_for_status()
            return response.json()["result"]

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
        return {item["symbol"]: Decimal(item["lastPrice"]) for item in await self._get("/api/v1/prices", symbols=",".join(symbols))}

    async def is_open(self, market: str, target: date) -> bool:
        result = await self._get(f"/api/v1/market-calendar/{market}", date=target.isoformat())
        return bool(result["today"].get("integrated") or result["today"].get("regularMarket"))

    async def create_order(self, payload: dict) -> str:
        token = await self._token()
        headers = {"Authorization": f"Bearer {token}", "X-Tossinvest-Account": await self._account_seq()}
        async with httpx.AsyncClient(base_url=self.config.api_base_url, timeout=15) as client:
            response = await client.post("/api/v1/orders", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["result"]["orderId"]
