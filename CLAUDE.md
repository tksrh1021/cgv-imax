# CGV 용산아이파크몰 IMAX 오디세이 알림봇 — 확정 사실

Phase 1b 실측으로 검증 완료된 사실만 기록한다. 전체 설계는 `docs/plan.json` 참조 (재조사 금지).

## 엔드포인트

```
GET https://cgv.co.kr/api/v1/booking/searchSchByMov
```

인증 토큰·서명·CSRF 없음. 단순 쿼리 파라미터 GET (Track A).
요청 1건당 `scnYmd` 하루치 응답.

## 필수 파라미터 5종 (전부 required, 생략 불가)

| 이름 | 값 | 의미 |
|---|---|---|
| `coCd` | `A420` | 회사코드 (CGV 고정) |
| `siteNo` | `0013` | 용산아이파크몰 |
| `scnYmd` | `YYYYMMDD` | 조회 날짜 (순회 대상) |
| `movNo` | `30001323` | 오디세이 |
| `rtctlScopCd` | `08` | **발매통제범위코드**. 생략 시 HTTP 400: `"발매통제범위코드는 필수 요청 파라미터 입니다."` |

`custNo`(개인 회원번호)는 **영구 제외**. 없어도 statusCode 0 정상 응답 확인됨. 코드·설정·커밋 어디에도 다시 추가하지 말 것.

## 필드 매핑

응답: `{"statusCode": 0, "statusMessage": "...", "data": [...]}` — `statusCode`가 0이면 정상, `data`가 빈 배열이면 해당 날짜 미오픈.

| 필드 | 의미 |
|---|---|
| `scnYmd` | 상영일자 (YYYYMMDD 문자열) |
| `scnsrtTm` | 상영 시작시각 (HHMM) — 24시 초과 주의 |
| `scnendTm` | 상영 종료시각 (HHMM) — 24시 초과 주의 |
| `salEndTm` | 판매 종료시각 (HHMM) — 24시 초과 주의 |
| `siteNo` | 지점코드 (`0013`=용산아이파크몰, `P013`=씨네드쉐프 용산 → 제외) |
| `scnsNo` | 상영관 코드 (`018`=IMAX관) |
| `scnsNm` | 상영관명 (`IMAX관`) |
| `stcnt` / `cpSeatCnt` | 총 좌석수 (IMAX관 624) |
| `frSeatCnt` | 잔여 좌석수 — 취소표 감지 기준 |
| `movNm` | 영화명 (`오디세이`) |
| `prodNm` | 상품명 (`오디세이(IMAX LASER 2D)`) |
| `movkndCd` | `48`=IMAX LASER 2D |
| `prodNo` | `20054745`=IMAX 상품코드 |

IMAX 필터 기준: **`scnsNo == '018' AND scnsNm == 'IMAX관'`**. `tcscnsGradNm == '아이맥스'`는 보조 지표일 뿐 필터 기준으로 쓰지 않는다.

## P013 제외 규칙

`siteNo=0013`을 요청 파라미터로 넣어도 **서버가 필터링하지 않고** 씨네드쉐프 용산(`siteNo=P013`)을 같은 응답에 섞어서 반환한다. 클라이언트에서 반드시 `siteNo == '0013'`으로 재필터링할 것. (실측: IMAX(`scnsNo=018`)는 지금까지 항상 `siteNo=0013`에만 존재하고 P013에는 나타난 적 없지만, 규칙 자체는 계속 유지한다.)

## 24시 초과 시각 규칙

`scnsrtTm`/`scnendTm`/`salEndTm`에 `2500`, `2802`, `2405` 같은 24시 초과 값이 실재한다 (익일 새벽 상영). 처리 규칙:

```
HH = int(value[:2])
if HH >= 24:
    HH -= 24
    date += 1일
```

이 처리를 빠뜨리면 심야 IMAX 회차가 파싱 예외로 죽거나 통째로 누락된다. 단위 테스트에 `2500` 케이스 필수.

## 죽은 엔드포인트 (재시도 금지)

- `http://www.cgv.co.kr/common/showtimes/iframeTheater.aspx` (301)
- `http://m.cgv.co.kr/Schedule/` (301)

## horizon 스냅샷 (참고용, 하드코딩 금지)

2026-09-18 기준 IMAX 오디세이 horizon = **2026-09-22**. 매번 런타임에 재계산해야 하는 값이다.
