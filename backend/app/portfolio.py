from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class Asset:
    symbol: str
    market: str
    weight: Decimal


ASSETS = (
    Asset("005930", "KR", Decimal("4")), Asset("000660", "KR", Decimal("3")),
    Asset("207940", "KR", Decimal("3")), Asset("005380", "KR", Decimal("3")),
    Asset("277810", "KR", Decimal("1")), Asset("105560", "KR", Decimal("1")),
    Asset("VOO", "US", Decimal("60")), Asset("GOOGL", "US", Decimal("6")),
    Asset("AMZN", "US", Decimal("5")), Asset("NVDA", "US", Decimal("4")),
    Asset("V", "US", Decimal("5")), Asset("BRK.B", "US", Decimal("5")),
)


def allocations(assets: tuple[Asset, ...], budgets: dict[str, Decimal]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for market in {asset.market for asset in assets}:
        group = [asset for asset in assets if asset.market == market]
        total = sum((asset.weight for asset in group), Decimal())
        for asset in group:
            result[asset.symbol] = (budgets[market] * asset.weight / total).quantize(Decimal("0.01"), ROUND_DOWN)
    return result


def kr_quantity(amount: Decimal, price: Decimal) -> Decimal:
    return (amount / price).to_integral_value(rounding=ROUND_DOWN) if price > 0 else Decimal()
