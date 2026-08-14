from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MonthlyRun, OrderIntent, OrderStatus, RunStatus
from app.portfolio import ASSETS, allocations, kr_quantity
from app.toss import TossClient


async def next_open_day(client: TossClient, market: str, target: date) -> date:
    for offset in range(15):
        candidate = target.fromordinal(target.toordinal() + offset)
        if await client.is_open(market, candidate):
            return candidate
    raise RuntimeError(f"{market} 시장의 거래일을 찾지 못했습니다.")


async def create_plan(db: Session, client: TossClient, month: str) -> MonthlyRun:
    existing = db.scalar(select(MonthlyRun).where(MonthlyRun.month == month))
    if existing:
        return existing
    budgets = {"KR": await client.buying_power("KRW"), "US": await client.buying_power("USD")}
    targets = allocations(ASSETS, budgets)
    run = MonthlyRun(month=month, krw_budget=budgets["KR"], usd_budget=budgets["US"])
    db.add(run)
    for asset in ASSETS:
        db.add(OrderIntent(month=month, symbol=asset.symbol, market=asset.market, target_amount=targets[asset.symbol]))
    db.commit()
    return run


async def execute_plan(db: Session, client: TossClient, month: str, market: str, live: bool) -> list[OrderIntent]:
    intents = list(db.scalars(select(OrderIntent).where(OrderIntent.month == month, OrderIntent.market == market, OrderIntent.status == OrderStatus.PLANNED)))
    prices = await client.prices([item.symbol for item in intents]) if market == "KR" else {}
    for item in intents:
        try:
            client_order_id = f"{month.replace('-', '')}-{item.symbol}"[:36]
            if item.market == "KR":
                item.quantity = kr_quantity(Decimal(item.target_amount), prices[item.symbol])
                if not item.quantity:
                    item.status, item.message = OrderStatus.SKIPPED, "예산이 1주 가격보다 작습니다."
                    continue
                payload = {"clientOrderId": client_order_id, "symbol": item.symbol, "side": "BUY", "orderType": "MARKET", "quantity": str(item.quantity)}
            else:
                payload = {"clientOrderId": client_order_id, "symbol": item.symbol, "side": "BUY", "orderType": "MARKET", "orderAmount": str(item.target_amount)}
            if live:
                item.toss_order_id, item.status = await client.create_order(payload), OrderStatus.SUBMITTED
            else:
                item.message = "DRY_RUN: 주문을 보내지 않았습니다."
        except Exception as error:
            item.status, item.message = OrderStatus.FAILED, str(error)[:500]
    db.commit()
    return intents
