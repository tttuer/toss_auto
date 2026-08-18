import asyncio
from datetime import date
from decimal import Decimal

import httpx

from app.config import Settings
from app.portfolio import ASSETS, allocations, kr_quantity
from app.toss import TossClient


def test_allocations_use_each_currency_balance():
    values = allocations(ASSETS, {"KR": Decimal("1350000"), "US": Decimal("7650")})
    assert values["005930"] == Decimal("360000.00")
    assert values["VOO"] == Decimal("5400.00")
    assert sum(values[item.symbol] for item in ASSETS if item.market == "US") == Decimal("7650.00")


def test_korean_stock_rounds_down_to_whole_share():
    assert kr_quantity(Decimal("360000"), Decimal("73000")) == 4


def test_market_calendar_is_cached_for_the_same_day():
    async def check():
        client = TossClient(Settings())
        calls = 0

        async def get_calendar(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return {"today": {"regularMarket": {}}}

        client._get = get_calendar  # type: ignore[method-assign]
        target = date(2026, 8, 18)
        await client.market_calendar("KR", target)
        await client.market_calendar("KR", target)
        assert calls == 1

    asyncio.run(check())


def test_toss_error_message_contains_the_server_reason():
    response = httpx.Response(422, json={"error": {"code": "insufficient-buying-power", "message": "주문 가능 금액이 부족합니다."}})
    assert TossClient._error_message(response) == "insufficient-buying-power: 주문 가능 금액이 부족합니다."


def test_prices_falls_back_to_individual_requests_after_batch_bad_request():
    async def check():
        client = TossClient(Settings())
        calls: list[str] = []

        async def get_prices(_path, **params):
            symbols = params["symbols"]
            calls.append(symbols)
            if "," in symbols:
                request = httpx.Request("GET", "https://example.test/api/v1/prices")
                response = httpx.Response(400, request=request)
                raise httpx.HTTPStatusError("bad request", request=request, response=response)
            return [{"symbol": symbols, "lastPrice": "100"}]

        client._get = get_prices  # type: ignore[method-assign]
        assert await client.prices(["005930", "000660"]) == {"005930": Decimal("100"), "000660": Decimal("100")}
        assert calls == ["005930,000660", "005930", "000660"]

    asyncio.run(check())
