from datetime import date, datetime, timedelta

BASELINE_INTERVAL_SEC = 15
BURST_INTERVAL_SEC = 20
BURST_DURATION_MIN = 30

BASELINE_BEFORE_DAYS = 2
BASELINE_AFTER_DAYS = 3
BURST_BEFORE_DAYS = 1
BURST_AFTER_DAYS = 5
FULL_SCAN_DAYS = 35


def is_burst_active(now: datetime, burst_until: datetime | None) -> bool:
    return burst_until is not None and now < burst_until


def start_burst(now: datetime) -> datetime:
    return now + timedelta(minutes=BURST_DURATION_MIN)


def scan_dates(mode: str, today: date, horizon: date | None) -> list[str]:
    if mode == "full_scan":
        return [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(FULL_SCAN_DAYS + 1)]

    if mode == "baseline":
        before, after = BASELINE_BEFORE_DAYS, BASELINE_AFTER_DAYS
    elif mode == "burst":
        before, after = BURST_BEFORE_DAYS, BURST_AFTER_DAYS
    else:
        raise ValueError(f"unknown mode: {mode}")

    anchor = horizon if horizon is not None else today
    anchor = max(anchor, today)

    start = max(anchor - timedelta(days=before), today)
    end = anchor + timedelta(days=after)

    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return dates
