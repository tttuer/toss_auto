import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Notification, OrderIntent, OrderStatus


logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, config: Settings):
        self.config = config

    async def send_once(self, db: Session, event_key: str, text: str) -> None:
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            return
        if db.scalar(select(Notification.id).where(Notification.event_key == event_key)):
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage",
                    json={"chat_id": self.config.telegram_chat_id, "text": text},
                )
                response.raise_for_status()
                if not response.json().get("ok"):
                    logger.warning("텔레그램 알림 전송 거절: %s", response.json().get("description", "알 수 없는 오류"))
                    return
            db.add(Notification(event_key=event_key))
            db.commit()
        except httpx.HTTPError as error:
            logger.warning("텔레그램 알림 전송 실패: %s", type(error).__name__)

    async def execution_summary(self, db: Session, month: str, market: str, intents: list[OrderIntent], live: bool) -> None:
        if not intents:
            return
        submitted = [item.symbol for item in intents if item.status == OrderStatus.SUBMITTED]
        failed = [f"{item.symbol} ({item.message or '사유 미확인'})" for item in intents if item.status == OrderStatus.FAILED]
        skipped = [item.symbol for item in intents if item.status == OrderStatus.SKIPPED]
        title = "주문 접수 결과" if live else "모의 주문 결과"
        lines = [f"[토스 자동투자] {month} {market}", title]
        if submitted:
            lines.append(f"접수: {', '.join(submitted)}")
        if failed:
            lines.append(f"실패: {', '.join(failed)}")
        if skipped:
            lines.append(f"건너뜀: {', '.join(skipped)}")
        await self.send_once(db, f"execution:{month}:{market}", "\n".join(lines))

    async def rate_limit_warning(self, db: Session, event_key: str, message: str) -> None:
        await self.send_once(db, event_key, f"[토스 자동투자] 실행 점검 실패\n{message}")
