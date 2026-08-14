from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, session
from app.models import MonthlyRun, OrderIntent
from app.service import create_plan, execute_plan, next_open_day
from app.toss import TossClient


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Toss 자동 투자", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def client() -> TossClient:
    config = settings()
    if not all((config.toss_client_id, config.toss_client_secret)):
        raise HTTPException(503, "토스 API 환경 변수가 설정되지 않았습니다.")
    return TossClient(config)


@app.get("/api/health")
def health():
    return {"ok": True, "liveTrading": settings().live_trading}


@app.get("/api/accounts")
async def accounts():
    """최초 1회 계좌를 찾아 TOSS_ACCOUNT_SEQ를 설정할 때 사용합니다."""
    return await client().accounts()


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(session)):
    return {"runs": list(db.scalars(select(MonthlyRun).order_by(MonthlyRun.month.desc()))), "orders": list(db.scalars(select(OrderIntent).order_by(OrderIntent.created_at.desc()).limit(100)))}


@app.post("/api/runs/{month}/plan")
async def plan(month: str, db: Session = Depends(session)):
    return await create_plan(db, client(), month)


@app.post("/api/runs/{month}/execute")
async def execute(month: str, market: str, db: Session = Depends(session)):
    if market not in {"KR", "US"}:
        raise HTTPException(400, "market은 KR 또는 US여야 합니다.")
    return await execute_plan(db, client(), month, market, settings().live_trading)


@app.get("/api/next-trading-days")
async def next_days():
    toss = client()
    target = date.today().replace(day=settings().investment_day)
    return {market: (await next_open_day(toss, market, target)).isoformat() for market in ("KR", "US")}
