"""k3s CronJob이 10분마다 실행하는 월간 주문 확인기."""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.database import SessionLocal, init_db
from app.service import create_plan, execute_plan, next_open_day
from app.telegram import TelegramNotifier
from app.toss import RateLimitExceeded, TossClient


logger = logging.getLogger(__name__)


async def run() -> None:
    config = settings()
    if not config.auto_run_enabled or not all((config.toss_client_id, config.toss_client_secret)):
        return
    init_db()
    toss = TossClient(config)
    telegram = TelegramNotifier(config)
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    try:
        with SessionLocal() as db:
            for market, timezone in (("KR", "Asia/Seoul"), ("US", "America/New_York")):
                local_today = now.astimezone(ZoneInfo(timezone)).date()
                target = local_today.replace(day=config.investment_day)
                if local_today != await next_open_day(toss, market, target):
                    continue
                # 같은 날짜는 next_open_day에서 이미 조회해 캐시한 값을 다시 사용합니다.
                calendar = await toss.market_calendar(market, local_today)
                regular = calendar["today"].get("integrated", calendar["today"]).get("regularMarket")
                if regular and now.isoformat() >= regular["startTime"]:
                    month = local_today.strftime("%Y-%m")
                    await create_plan(db, toss, month)
                    intents = await execute_plan(db, toss, month, market, config.live_trading)
                    await telegram.execution_summary(db, month, market, intents, config.live_trading)
    except RateLimitExceeded as error:
        logger.warning("토스 호출 한도 때문에 이번 점검을 건너뜁니다: %s", error)
        with SessionLocal() as db:
            await telegram.rate_limit_warning(db, f"rate-limit:{now.date().isoformat()}", str(error))


if __name__ == "__main__":
    asyncio.run(run())
