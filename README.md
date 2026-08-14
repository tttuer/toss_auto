# Toss 자동 투자

매월 16일(휴장일이면 다음 거래일)에 토스증권 계좌의 실제 KRW/USD 매수 가능 금액을 기준으로 포트폴리오를 배분하는 자동 투자 도구입니다.

기본값은 실제 주문입니다. `AUTO_RUN_ENABLED=true`와 `LIVE_TRADING=true`이면 실제 주문을 보냅니다.

## 실행

```powershell
uv run --directory backend uvicorn app.main:app --reload --port 8000
pnpm --dir frontend install
pnpm --dir frontend dev
```

로컬 API 문서: `http://localhost:8000/docs`

## 핵심 규칙

- 국내 자산은 KRW 매수 가능 금액을 `4:3:3:3:1:1`로 나눕니다.
- 미국 자산은 USD 매수 가능 금액을 `60:6:5:4:5:5`로 나눕니다.
- 미국은 금액 시장가 주문, 국내는 현재가 이하 정수 수량 시장가 주문을 사용합니다.
- 월별·종목별 주문 계획을 먼저 저장해 중복 주문을 막습니다.
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
```

`DATABASE_URL`은 배포 과정에서 `POSTGRES_USER`와 `POSTGRES_PASSWORD`로 자동 생성합니다.

계좌가 하나라면 `TOSS_ACCOUNT_SEQ`를 설정할 필요가 없습니다. 주문을 시작하기 전 계좌 목록을 조회하고, 반환된 유일한 계좌의 `accountSeq`를 그 실행에서 자동으로 사용합니다. 계좌가 둘 이상일 때만 오주문 방지를 위해 `TOSS_ACCOUNT_SEQ`를 직접 설정해야 합니다.
