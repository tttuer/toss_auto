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
    Asset("VOO", "US", Decimal("640.5")), Asset("GOOGL", "US", Decimal("78")),
    Asset("AMZN", "US", Decimal("65")), Asset("NVDA", "US", Decimal("52")),
    Asset("V", "US", Decimal("65")), Asset("BRK.B", "US", Decimal("274.5")),
    Asset("QNT", "US", Decimal("60")), Asset("IONQ", "US", Decimal("40")),
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


def balanced_kr_allocations(
    assets: tuple[Asset, ...], prices: dict[str, Decimal], automatic_values: dict[str, Decimal], budget: Decimal
) -> dict[str, Decimal]:
    """Buy whole shares that move automatic-investment values nearest to their target weights."""
    group = [asset for asset in assets if asset.market == "KR" and prices.get(asset.symbol, Decimal()) > 0]
    planned = {asset.symbol: Decimal() for asset in group}
    total_weight = sum((asset.weight for asset in group), Decimal())
    remaining = budget
    while choices := [asset for asset in group if prices[asset.symbol] <= remaining]:
        def score(asset: Asset) -> tuple[Decimal, Decimal, str]:
            total = sum((automatic_values.get(item.symbol, Decimal()) + planned[item.symbol] for item in group), prices[asset.symbol])
            error = sum(
                ((automatic_values.get(item.symbol, Decimal()) + planned[item.symbol] + (prices[asset.symbol] if item == asset else Decimal()) - total * item.weight / total_weight) / total) ** 2
                for item in group
            )
            return error, -prices[asset.symbol], asset.symbol

        selected = min(choices, key=score)
        planned[selected.symbol] += prices[selected.symbol]
        remaining -= prices[selected.symbol]
    return planned
