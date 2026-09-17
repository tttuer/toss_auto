# Toss 자동 투자

매월 16일(휴장일이면 다음 거래일)에 토스증권 계좌의 실제 KRW/USD 매수 가능 금액을 기준으로 포트폴리오를 배분하는 자동 투자 도구입니다. 현재 배포는 API·PostgreSQL·자동 실행기만 포함하며 웹 화면은 배포하지 않습니다.

기본값은 실제 주문입니다. `AUTO_RUN_ENABLED=true`와 `LIVE_TRADING=true`이면 실제 주문을 보냅니다.

## 실행

```powershell
uv run --directory backend uvicorn app.main:app --reload --port 8000
pnpm --dir frontend install
pnpm --dir frontend dev
```

로컬 API 문서: `http://localhost:8000/docs`

## 핵심 규칙

- 국내는 토스의 실제 KRW 매수 가능 금액을 확인합니다. 월 135만 원과 자동투자에서 이월된 미집행 금액 안에서, 이 프로그램이 접수한 주문 기록만 기준으로 목표 비중 `4:3:3:3:1:1`에 가장 가까워지도록 살 수 있는 정수 주식을 고릅니다. 수동 매수는 계산에 넣지 않으므로, 한 종목의 몫이 1주에 모자라도 남은 돈으로 다른 종목을 먼저 삽니다.
- 국내 신규 투자 예산은 월 135만 원이며, 미국 신규 투자 예산은 월 765만 원을 당일 환율로 환산한 달러 한도입니다.
- 미국 자산은 월 765만 원 한도 안에서 VOO·버크셔(BRK.B) 합계 549만 원을 70:30으로 나눠 각각 384.3만 원·164.7만 원을 투자합니다. 나머지 해외 개별주는 156만 원, 양자컴퓨팅은 60만 원이며 QNT 36만 원(60%), IONQ 24만 원(40%)입니다.
- 미국은 금액 시장가 주문, 국내는 현재가 이하 정수 수량 시장가 주문을 사용합니다.
- 미국 주문은 VOO, BRK.B 순서로 요청합니다. 금액 주문이 가능한 미국 정규장 마감 1시간 전까지만 자동 주문합니다.
- 월별·종목별 주문 계획을 먼저 저장해 중복 주문을 막습니다.
- 예정 투자일에 실행을 놓쳐도 해당 월 주문 계획이 없으면 이후 개장일에 다시 시도합니다. CronJob 로그와 완료 Job은 7일간 보관합니다.
- 이전에 토스가 명확히 거절한 주문은 다음 정기 투자일의 신규 주문 뒤에 보충합니다. 환전은 자동으로 하지 않으며, 실제 매수 가능 금액이 부족하면 신규 주문 예산을 줄입니다.
- 실제 주문 전 토스 WTS에 k3s 서버의 고정 공인 IP를 허용 IP로 등록해야 합니다.

`AUTO_RUN_ENABLED=true`와 `LIVE_TRADING=true` GitHub Secret을 모두 넣으면 k3s CronJob이 10분마다 확인합니다. 둘 중 하나라도 빠지거나 `false`면 실제 주문을 보내지 않습니다. 16일이 휴장일이면 토스 장 캘린더의 다음 거래일, 각 시장의 정규장 시작 후에만 주문합니다.

GitHub Actions Secrets에 아래 값을 각각 만드세요. 실행 값은 따로 만들지 않으면 기본으로 `true`가 적용됩니다.

```text
CLIENT_ID=...
CLIENT_SECRET=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
AUTO_RUN_ENABLED=true
LIVE_TRADING=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

`DATABASE_URL`은 배포 과정에서 `POSTGRES_USER`와 `POSTGRES_PASSWORD`로 자동 생성합니다.

텔레그램은 주문 접수 결과, 실패·건너뜀, 토스 API 호출 제한 오류만 보냅니다. `@BotFather`에서 만든 봇의 토큰과, 봇에게 `/start`를 보낸 채팅의 ID를 GitHub Secret `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`에 넣으세요. 두 값 중 하나라도 비어 있으면 알림은 보내지 않습니다.

계좌가 하나라면 `TOSS_ACCOUNT_SEQ`를 설정할 필요가 없습니다. 주문을 시작하기 전 계좌 목록을 조회하고, 반환된 유일한 계좌의 `accountSeq`를 그 실행에서 자동으로 사용합니다. 계좌가 둘 이상일 때만 오주문 방지를 위해 `TOSS_ACCOUNT_SEQ`를 직접 설정해야 합니다.

도메인을 정한 뒤에만 `k8s/overlays/prod/kustomization.yaml`에 `ingress.yaml`을 다시 추가하고, 호스트·TLS 값을 채우세요.
