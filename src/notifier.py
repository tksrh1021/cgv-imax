import os
from datetime import datetime

import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
BOOKING_URL = "https://cgv.co.kr/cnm/movieBook/cinema?theaterCode=0013"
BOOKING_LIMIT_NOTE = "예매 제한: 1회 최대 4매 / 1일 최대 4매 (CGV 한시 운영)"
CANCELLATION_THROTTLE_SEC = 600


class TelegramNotConfigured(Exception):
    pass


def _credentials() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 없습니다")
    return token, chat_id


def send_message(text: str) -> None:
    token, chat_id = _credentials()
    url = TELEGRAM_API.format(token=token)
    httpx.post(url, data={"chat_id": chat_id, "text": text}, timeout=10.0)


def _format_showtime_line(s) -> str:
    return f"{s.date} {s.start_time} | {s.screen_name} | 잔여 {s.seats_remaining}/{s.seats_total}석"


def _event_id(event: dict) -> str:
    rule = event["rule"]
    if rule == "booking_horizon_extended":
        return f"{rule}:{event['new_horizon']}"
    if rule == "new_showtime":
        keys = ",".join(sorted(s.key for s in event["new_showtimes"]))
        return f"{rule}:{keys}"
    if rule == "cancellation_seat":
        return f"{rule}:{event['showtime'].key}"
    if rule in ("silent_zero_result", "fetch_failure_streak"):
        return f"{rule}:{event['streak']}"
    return f"{rule}:{event}"


def _message_for_event(event: dict, detected_at_kst: str) -> str:
    rule = event["rule"]
    if rule == "booking_horizon_extended":
        title = "예매 오픈 발생 (예매 가능 범위 확장)"
        body = f"{event['previous_horizon']} → {event['new_horizon']}"
    elif rule == "new_showtime":
        title = "신규 회차 오픈"
        body = "\n".join(_format_showtime_line(s) for s in event["new_showtimes"])
    elif rule == "cancellation_seat":
        title = "취소표 발생"
        body = _format_showtime_line(event["showtime"])
    elif rule == "silent_zero_result":
        title = "수집 이상 — 필드값 변경 또는 종영 의심"
        body = f"IMAX 오디세이 조회 결과가 {event['streak']}회 연속 0건입니다."
    elif rule == "fetch_failure_streak":
        title = "수집 실패 — API 구조 변경 의심"
        body = f"요청이 {event['streak']}회 연속 실패했습니다."
    else:
        title = rule
        body = str(event)

    return (
        f"🎬 용아맥 오디세이 — {title}\n\n"
        f"{body}\n\n"
        f"감지시각(KST): {detected_at_kst}\n"
        f"{BOOKING_LIMIT_NOTE}\n"
        f"{BOOKING_URL}"
    )


def notify_events(events: list[dict], notified_state: dict, now: datetime) -> bool:
    """notified_state 는 {event_id: iso_timestamp} 이며 in-place로 갱신된다.
    실제로 한 건 이상 발송했으면 True를 반환한다.
    """
    sent_any = False
    now_iso = now.isoformat()

    for event in events:
        event_id = _event_id(event)
        rule = event["rule"]

        if rule == "cancellation_seat":
            last_sent = notified_state.get(event_id)
            if last_sent:
                elapsed = (now - datetime.fromisoformat(last_sent)).total_seconds()
                if elapsed < CANCELLATION_THROTTLE_SEC:
                    continue
        elif event_id in notified_state:
            continue

        send_message(_message_for_event(event, now_iso))
        notified_state[event_id] = now_iso
        sent_any = True

    return sent_any


def send_access_denied_alert() -> None:
    send_message("🚨 CGV 접근 거부 감지 (403/429/CAPTCHA) — 폴링을 즉시 중단합니다. 확인이 필요합니다.")


def send_heartbeat(horizon: str | None) -> None:
    send_message(f"✅ 용아맥 오디세이 감시 정상 동작 중\n현재 horizon: {horizon or '알 수 없음'}")
