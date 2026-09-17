"""k3s CronJob이 10분마다 실행하는 월간 주문 확인기."""
import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.database import SessionLocal, init_db
from app.service import catch_up_orders, create_plan, execute_plan, next_open_day
from app.telegram import TelegramNotifier
from app.toss import RateLimitExceeded, TossClient


logger = logging.getLogger(__name__)


def is_order_window_open(market: str, now: datetime, regular: dict[str, str]) -> bool:
    start = datetime.fromisoformat(regular["startTime"])
    end = datetime.fromisoformat(regular["endTime"])
    cutoff = end - timedelta(hours=1) if market == "US" else end
    return start <= now < cutoff


def is_due(local_today: date, scheduled_day: date) -> bool:
    return local_today >= scheduled_day


async def run() -> None:
    config = settings()
    if not config.auto_run_enabled:
        logger.warning("자동 주문이 AUTO_RUN_ENABLED=false로 비활성화되어 있습니다.")
        return
    if not all((config.toss_client_id, config.toss_client_secret)):
        logger.error("토스 API 인증 정보가 없어 자동 주문을 건너뜁니다.")
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
                scheduled_day = await next_open_day(toss, market, target)
                if not is_due(local_today, scheduled_day):
                    logger.info("%s 주문 대기: 예정일 %s", market, scheduled_day)
                    continue
                # 같은 날짜는 next_open_day에서 이미 조회해 캐시한 값을 다시 사용합니다.
                calendar = await toss.market_calendar(market, local_today)
                regular = calendar["today"].get("integrated", calendar["today"]).get("regularMarket")
                if not regular:
                    logger.info("%s 주문 대기: 정규장이 아닙니다.", market)
                    continue
                if not is_order_window_open(market, now, regular):
                    logger.info("%s 주문 대기: 주문 가능 시간이 아닙니다.", market)
                    continue
                month = local_today.strftime("%Y-%m")
                logger.info("%s %s 주문을 실행합니다.", month, market)
                await create_plan(db, toss, month)
                intents = await execute_plan(db, toss, month, market, config.live_trading)
                if local_today == scheduled_day:
                    intents += await catch_up_orders(db, toss, month, market, config.live_trading)
                await telegram.execution_summary(db, month, market, intents, config.live_trading)
    except RateLimitExceeded as error:
        logger.warning("토스 호출 한도 때문에 이번 점검을 건너뜁니다: %s", error)
        with SessionLocal() as db:
            await telegram.rate_limit_warning(db, f"rate-limit:{now.date().isoformat()}", str(error))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
