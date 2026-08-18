import asyncio
from datetime import date
from decimal import Decimal

import httpx

from app.config import Settings
from app.models import OrderIntent, OrderStatus
from app.portfolio import ASSETS, allocations, kr_quantity
from app.telegram import TelegramNotifier
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


def test_telegram_summary_only_contains_important_statuses():
    async def check():
        notifier = TelegramNotifier(Settings())
        sent: list[tuple[str, str]] = []

        async def send_once(_db, event_key, text):
            sent.append((event_key, text))

        notifier.send_once = send_once  # type: ignore[method-assign]
        intents = [
            OrderIntent(symbol="VOO", market="US", month="2026-08", target_amount=Decimal("60"), status=OrderStatus.SUBMITTED),
            OrderIntent(symbol="BRK.B", market="US", month="2026-08", target_amount=Decimal("5"), status=OrderStatus.FAILED, message="주문 가능 금액 부족"),
        ]
        await notifier.execution_summary(None, "2026-08", "US", intents, True)
        assert sent == [("execution:2026-08:US", "[토스 자동투자] 2026-08 US\n주문 접수 결과\n접수: VOO\n실패: BRK.B (주문 가능 금액 부족)")]

    asyncio.run(check())


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
