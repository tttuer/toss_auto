from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OrderStatus(StrEnum):
    PLANNED = "PLANNED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class MonthlyRun(Base):
    __tablename__ = "monthly_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), unique=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.PLANNED)
    krw_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    usd_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OrderIntent(Base):
    __tablename__ = "order_intents"
    __table_args__ = (UniqueConstraint("month", "symbol", name="uq_month_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7))
    symbol: Mapped[str] = mapped_column(String(16))
    market: Mapped[str] = mapped_column(String(2))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PLANNED)
    toss_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
