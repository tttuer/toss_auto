"""k3s CronJob이 10분마다 실행하는 월간 주문 확인기."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.database import SessionLocal, init_db
from app.service import create_plan, execute_plan, next_open_day
from app.toss import TossClient


async def run() -> None:
    config = settings()
    if not config.auto_run_enabled or not all((config.toss_client_id, config.toss_client_secret)):
        return
    init_db()
    toss = TossClient(config)
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    with SessionLocal() as db:
        for market, timezone in (("KR", "Asia/Seoul"), ("US", "America/New_York")):
            local_today = now.astimezone(ZoneInfo(timezone)).date()
            target = local_today.replace(day=config.investment_day)
            if local_today != await next_open_day(toss, market, target):
                continue
            # 토스 장 캘린더가 정규장 시작 시간을 제공하므로 서머타임도 따로 계산하지 않습니다.
            calendar = await toss._get(f"/api/v1/market-calendar/{market}", date=local_today.isoformat())
            regular = calendar["today"].get("integrated", calendar["today"]).get("regularMarket")
            if regular and now.isoformat() >= regular["startTime"]:
                month = local_today.strftime("%Y-%m")
                await create_plan(db, toss, month)
                await execute_plan(db, toss, month, market, config.live_trading)


if __name__ == "__main__":
    asyncio.run(run())
