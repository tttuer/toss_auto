from decimal import Decimal

from app.portfolio import ASSETS, allocations, kr_quantity


def test_allocations_use_each_currency_balance():
    values = allocations(ASSETS, {"KR": Decimal("1350000"), "US": Decimal("7650")})
    assert values["005930"] == Decimal("360000.00")
    assert values["VOO"] == Decimal("5400.00")
    assert sum(values[item.symbol] for item in ASSETS if item.market == "US") == Decimal("7650.00")


def test_korean_stock_rounds_down_to_whole_share():
    assert kr_quantity(Decimal("360000"), Decimal("73000")) == 4
