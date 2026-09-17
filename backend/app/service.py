from datetime import date
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Carryover, MonthlyRun, OrderIntent, OrderStatus, RunStatus
from app.portfolio import ASSETS, allocations, balanced_kr_allocations, kr_quantity
from app.toss import TossClient


def client_order_id(month: str, symbol: str) -> str:
    return f"{month.replace('-', '')}-{symbol.replace('.', '-')}"[:36]


def investment_order(intents: list[OrderIntent]) -> list[OrderIntent]:
    priority = {"VOO": 0, "BRK.B": 1}
    return sorted(intents, key=lambda item: (priority.get(item.symbol, 2), item.id or 0))


def budget_after_catch_up(available: Decimal, monthly_limit: Decimal, catch_up: Decimal) -> Decimal:
    return min(monthly_limit, max(Decimal(), available - catch_up))


def spent_amount(intents: list[OrderIntent]) -> Decimal:
    return sum((item.target_amount for item in intents if item.status in {OrderStatus.SUBMITTED, OrderStatus.FILLED}), Decimal())


def kr_carryover(db: Session, month: str) -> Carryover:
    carryover = db.get(Carryover, "KR")
    if carryover:
        return carryover
    previous_runs = list(db.scalars(select(MonthlyRun).where(MonthlyRun.month < month)))
    amount = sum(
        (max(Decimal(), run.krw_budget - spent_amount(list(db.scalars(select(OrderIntent).where(OrderIntent.month == run.month, OrderIntent.market == "KR"))))) for run in previous_runs),
        Decimal(),
    )
    carryover = Carryover(market="KR", amount=amount)
    db.add(carryover)
    return carryover


def automatic_kr_values(db: Session, month: str) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    orders = db.scalars(select(OrderIntent).where(
        OrderIntent.month <= month, OrderIntent.market == "KR",
        OrderIntent.status.in_((OrderStatus.SUBMITTED, OrderStatus.FILLED)),
    ))
    for order in orders:
        values[order.symbol] = values.get(order.symbol, Decimal()) + order.target_amount
    return values


async def kr_targets(db: Session, client: TossClient, month: str, budget: Decimal) -> dict[str, Decimal]:
    assets = tuple(asset for asset in ASSETS if asset.market == "KR")
    prices = await client.prices([asset.symbol for asset in assets])
    return balanced_kr_allocations(assets, prices, automatic_kr_values(db, month), budget)


async def refresh_kr_plan(db: Session, client: TossClient, run: MonthlyRun) -> None:
    intents = list(db.scalars(select(OrderIntent).where(OrderIntent.month == run.month, OrderIntent.market == "KR")))
    spent = spent_amount(intents)
    remaining = max(Decimal(), run.krw_budget - spent)
    carryover = kr_carryover(db, run.month)
    available = await client.buying_power("KRW")
    if carryover.reserved_month != run.month:
        capacity = remaining + carryover.amount
        budget = min(available, capacity)
        carryover.amount = capacity - budget
        carryover.tracked_remaining = Decimal()
        carryover.reserved_month = run.month
        run.krw_budget = spent + budget
    else:
        budget = min(available, remaining)
    targets = await kr_targets(db, client, run.month, budget)
    for item in intents:
        if item.status not in {OrderStatus.SUBMITTED, OrderStatus.FILLED}:
            item.target_amount, item.quantity = targets[item.symbol], None
            item.status, item.message = OrderStatus.PLANNED, None
    db.commit()


def sync_kr_carryover(db: Session, month: str) -> None:
    run = db.scalar(select(MonthlyRun).where(MonthlyRun.month == month))
    if not run:
        return
    intents = list(db.scalars(select(OrderIntent).where(OrderIntent.month == month, OrderIntent.market == "KR")))
    remaining = max(Decimal(), run.krw_budget - spent_amount(intents))
    carryover = kr_carryover(db, month)
    carryover.amount = max(Decimal(), carryover.amount - carryover.tracked_remaining) + remaining
    carryover.tracked_remaining, carryover.reserved_month = remaining, month


def usd_budget_from_krw(krw_budget: Decimal, usd_krw_rate: Decimal) -> Decimal:
    return (krw_budget / usd_krw_rate).quantize(Decimal("0.01"), ROUND_DOWN)


def can_catch_up(intent: OrderIntent) -> bool:
    return intent.toss_order_id is None and bool(intent.message) and ("(400)" in intent.message or "(422)" in intent.message or "Client error '400" in intent.message or "Client error '422" in intent.message)


async def next_open_day(client: TossClient, market: str, target: date) -> date:
    for offset in range(15):
        candidate = target.fromordinal(target.toordinal() + offset)
        if await client.is_open(market, candidate):
            return candidate
    raise RuntimeError(f"{market} 시장의 거래일을 찾지 못했습니다.")


async def create_plan(db: Session, client: TossClient, month: str) -> MonthlyRun:
    existing = db.scalar(select(MonthlyRun).where(MonthlyRun.month == month))
    if existing:
        await refresh_kr_plan(db, client, existing)
        return existing
    pending = list(db.scalars(select(OrderIntent).where(OrderIntent.month < month, OrderIntent.status == OrderStatus.FAILED)))
    catch_up = {"US": sum((item.target_amount for item in pending if item.market == "US" and can_catch_up(item)), Decimal())}
    available = {"KR": await client.buying_power("KRW"), "US": await client.buying_power("USD")}
    us_limit = usd_budget_from_krw(client.config.monthly_us_krw_budget, await client.usd_krw_buy_rate())
    carryover = kr_carryover(db, month)
    kr_capacity = client.config.monthly_krw_budget + carryover.amount
    budgets = {
        "KR": min(available["KR"], kr_capacity),
        "US": budget_after_catch_up(available["US"], us_limit, catch_up["US"]),
    }
    carryover.amount, carryover.tracked_remaining, carryover.reserved_month = kr_capacity - budgets["KR"], Decimal(), month
    targets = allocations(ASSETS, budgets)
    targets.update(await kr_targets(db, client, month, budgets["KR"]))
    run = MonthlyRun(month=month, krw_budget=budgets["KR"], usd_budget=budgets["US"])
    db.add(run)
    for asset in ASSETS:
        db.add(OrderIntent(month=month, symbol=asset.symbol, market=asset.market, target_amount=targets[asset.symbol]))
    db.commit()
    return run


async def execute_plan(db: Session, client: TossClient, month: str, market: str, live: bool, intents: list[OrderIntent] | None = None) -> list[OrderIntent]:
    if intents is None:
        intents = list(db.scalars(select(OrderIntent).where(OrderIntent.month == month, OrderIntent.market == market, OrderIntent.status == OrderStatus.PLANNED)))
    intents = investment_order(intents)
    prices = await client.prices([item.symbol for item in intents]) if market == "KR" else {}
    for item in intents:
        try:
            order_id = client_order_id(month, item.symbol)
            if item.market == "KR":
                price = prices.get(item.symbol)
                if price is None:
                    item.status, item.message = OrderStatus.FAILED, "현재가 조회에 실패했습니다."
                    continue
                item.quantity = kr_quantity(Decimal(item.target_amount), price)
                if not item.quantity:
                    item.status, item.message = OrderStatus.SKIPPED, "남은 예산으로 1주를 살 수 없습니다."
                    continue
                item.target_amount = item.quantity * price
                payload = {"clientOrderId": order_id, "symbol": item.symbol, "side": "BUY", "orderType": "MARKET", "quantity": str(item.quantity)}
            else:
                payload = {"clientOrderId": order_id, "symbol": item.symbol, "side": "BUY", "orderType": "MARKET", "orderAmount": str(item.target_amount)}
            if live:
                item.toss_order_id, item.status = await client.create_order(payload), OrderStatus.SUBMITTED
            else:
                item.message = "DRY_RUN: 주문을 보내지 않았습니다."
        except Exception as error:
            item.status, item.message = OrderStatus.FAILED, str(error)[:500]
    db.commit()
    if market == "KR":
        sync_kr_carryover(db, month)
        db.commit()
    return intents


async def catch_up_orders(db: Session, client: TossClient, month: str, market: str, live: bool) -> list[OrderIntent]:
    if market == "KR":
        return []
    intents = [item for item in db.scalars(select(OrderIntent).where(OrderIntent.month < month, OrderIntent.market == market, OrderIntent.status == OrderStatus.FAILED)) if can_catch_up(item)]
    if not intents:
        return []
    currency = "KRW" if market == "KR" else "USD"
    if sum((item.target_amount for item in intents), Decimal()) > await client.buying_power(currency):
        return []
    return await execute_plan(db, client, month, market, live, intents)
