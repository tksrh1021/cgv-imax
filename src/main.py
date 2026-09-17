import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from src import notifier, scheduler
from src.differ import diff_snapshot, update_health_streaks
from src.fetcher import AccessDenied, FetchError, fetch_schedule
from src.parser import Showtime, parse_showtimes

KST = timezone(timedelta(hours=9))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")
SNAPSHOT_PATH = os.path.join(STATE_DIR, "snapshot.json")
BURST_UNTIL_PATH = os.path.join(STATE_DIR, "burst_until.json")
NOTIFIED_PATH = os.path.join(STATE_DIR, "notified.json")
HEALTH_PATH = os.path.join(STATE_DIR, "health.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")

BURST_LOOP_BUDGET_SEC = 290


def load_dotenv(path: str = ENV_PATH) -> None:
    """로컬 개발용 최소 .env 로더. GitHub Actions에서는 Secrets가 환경변수로 직접 주입되므로 사용되지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def showtime_to_dict(s: Showtime) -> dict:
    d = asdict(s)
    d["start_datetime"] = s.start_datetime.isoformat()
    return d


def showtime_from_dict(d: dict) -> Showtime:
    return Showtime(
        date=d["date"],
        start_time=d["start_time"],
        start_datetime=datetime.fromisoformat(d["start_datetime"]),
        screen_no=d["screen_no"],
        screen_name=d["screen_name"],
        movie_title=d["movie_title"],
        product_name=d["product_name"],
        seats_remaining=d["seats_remaining"],
        seats_total=d["seats_total"],
        key=d["key"],
    )


def determine_mode(forced_mode: str | None, burst_until_raw: str | None, now: datetime) -> str:
    if forced_mode == "full_scan":
        return "full_scan"
    burst_until = datetime.fromisoformat(burst_until_raw) if burst_until_raw else None
    if scheduler.is_burst_active(now, burst_until):
        return "burst"
    return "baseline"


def merge_showtimes(previous_showtime_dicts: list[dict], scanned_dates_iso: set, fresh: list[Showtime]) -> list[Showtime]:
    """scan_range 밖 날짜는 이전 스냅샷 값을 그대로 유지하고, scan_range 안 날짜만 새 값으로 교체한다."""
    kept = [showtime_from_dict(d) for d in previous_showtime_dicts if d["date"] not in scanned_dates_iso]
    return kept + fresh


def run_scan(dates: list[str], interval_sec: int) -> tuple[list[Showtime], int]:
    fetched: list[Showtime] = []
    failures = 0
    for i, scn_ymd in enumerate(dates):
        if i > 0:
            time.sleep(interval_sec)
        try:
            response = fetch_schedule(scn_ymd)
        except FetchError as exc:
            print(f"FETCH_ERROR date={scn_ymd}: {exc}")
            failures += 1
            continue
        fetched.extend(parse_showtimes(response))
    return fetched, failures


def run_cycle(mode: str, now: datetime, previous_snapshot: dict | None, notified_state: dict, health: dict):
    """수집 → diff → 알림 1회. (새 스냅샷, DiffResult, burst 트리거 이벤트|None, 실패건수) 반환."""
    previous_horizon = None
    if previous_snapshot and previous_snapshot.get("horizon"):
        previous_horizon = datetime.strptime(previous_snapshot["horizon"], "%Y-%m-%d").date()

    dates = scheduler.scan_dates(mode, now.date(), previous_horizon)
    interval_sec = scheduler.BURST_INTERVAL_SEC if mode == "burst" else scheduler.BASELINE_INTERVAL_SEC
    print(f"mode={mode} scan_dates={dates}")

    fresh_showtimes, failures = run_scan(dates, interval_sec)

    scanned_dates_iso = {datetime.strptime(d, "%Y%m%d").date().isoformat() for d in dates}
    previous_showtimes = previous_snapshot.get("showtimes", []) if previous_snapshot else []
    merged_current = merge_showtimes(previous_showtimes, scanned_dates_iso, fresh_showtimes)

    result = diff_snapshot(previous_snapshot, merged_current)

    health_events = update_health_streaks(
        health,
        cycle_had_zero_result=(len(fresh_showtimes) == 0),
        cycle_had_fetch_failure=(failures > 0),
    )

    notifier.notify_events(result.events + health_events, notified_state, now)

    burst_trigger = next(
        (e for e in result.events if e["rule"] in ("booking_horizon_extended", "new_showtime")),
        None,
    )

    new_snapshot = {
        "updated_at_kst": now.isoformat(),
        "horizon": result.horizon,
        "showtimes": [showtime_to_dict(s) for s in merged_current],
    }
    return new_snapshot, result, burst_trigger, failures


def main() -> int:
    load_dotenv()

    forced_mode = os.environ.get("MODE")
    loop_start = time.monotonic()

    previous_snapshot = load_json(SNAPSHOT_PATH, None)
    notified_state = load_json(NOTIFIED_PATH, {})
    burst_state = load_json(BURST_UNTIL_PATH, {})
    health = load_json(HEALTH_PATH, {})

    while True:
        now = now_kst()
        mode = determine_mode(forced_mode, burst_state.get("burst_until_kst"), now)

        try:
            new_snapshot, result, burst_trigger, failures = run_cycle(
                mode, now, previous_snapshot, notified_state, health
            )
        except AccessDenied as exc:
            print(f"ACCESS_DENIED: {exc} — 폴링을 즉시 중단합니다")
            notifier.send_access_denied_alert()
            save_json(NOTIFIED_PATH, notified_state)
            return 1

        previous_snapshot = new_snapshot
        save_json(SNAPSHOT_PATH, new_snapshot)
        save_json(NOTIFIED_PATH, notified_state)
        save_json(HEALTH_PATH, health)

        if burst_trigger is not None:
            burst_until = scheduler.start_burst(now)
            burst_state = {"burst_until_kst": burst_until.isoformat(), "triggered_by": burst_trigger["rule"]}
            save_json(BURST_UNTIL_PATH, burst_state)
            print(f"BURST_ENTER until={burst_until.isoformat()} triggered_by={burst_trigger['rule']}")

        print(f"done mode={mode} events={[e['rule'] for e in result.events]} horizon={result.horizon} failures={failures}")

        if mode != "burst":
            break  # baseline/full_scan은 1회만 수행. 다음 실행은 cron이 담당한다.

        if time.monotonic() - loop_start >= BURST_LOOP_BUDGET_SEC:
            print("BURST_BUDGET_EXHAUSTED — 이번 job 종료, 다음 cron 실행이 이어받는다")
            break

        if not scheduler.is_burst_active(now_kst(), datetime.fromisoformat(burst_state["burst_until_kst"])):
            print("BURST_EXPIRED — baseline으로 복귀")
            break

    if forced_mode == "full_scan":
        notifier.send_heartbeat(previous_snapshot.get("horizon") if previous_snapshot else None)

    return 0


if __name__ == "__main__":
    sys.exit(main())
