from dataclasses import dataclass, field

from src.parser import Showtime


@dataclass
class DiffResult:
    events: list = field(default_factory=list)
    horizon: str | None = None


def compute_horizon(showtimes: list[Showtime]) -> str | None:
    if not showtimes:
        return None
    return max(s.date for s in showtimes)


def diff_snapshot(previous: dict | None, current: list[Showtime]) -> DiffResult:
    new_horizon = compute_horizon(current)

    if previous is None:
        return DiffResult(events=[], horizon=new_horizon)

    events = []

    prev_horizon = previous.get("horizon")
    if prev_horizon and new_horizon and new_horizon > prev_horizon:
        events.append(
            {
                "rule": "booking_horizon_extended",
                "previous_horizon": prev_horizon,
                "new_horizon": new_horizon,
            }
        )

    prev_by_key = {s["key"]: s for s in previous.get("showtimes", [])}

    new_showtimes = [s for s in current if s.key not in prev_by_key]
    if new_showtimes:
        events.append({"rule": "new_showtime", "new_showtimes": new_showtimes})

    for s in current:
        prev = prev_by_key.get(s.key)
        if prev is not None and prev.get("seats_remaining") == 0 and s.seats_remaining >= 1:
            events.append({"rule": "cancellation_seat", "showtime": s})

    return DiffResult(events=events, horizon=new_horizon)


ZERO_RESULT_STREAK_THRESHOLD = 5
FETCH_FAILURE_STREAK_THRESHOLD = 5


def update_health_streaks(health: dict, *, cycle_had_zero_result: bool, cycle_had_fetch_failure: bool) -> list[dict]:
    """state/health.json 용 연속 카운터를 갱신하고, 임계값에 '막 도달한' 순간에만 경고 이벤트를 낸다.
    health 는 in-place로 갱신된다."""
    events = []

    if cycle_had_zero_result:
        health["zero_result_streak"] = health.get("zero_result_streak", 0) + 1
    else:
        health["zero_result_streak"] = 0
    if health["zero_result_streak"] == ZERO_RESULT_STREAK_THRESHOLD:
        events.append({"rule": "silent_zero_result", "streak": health["zero_result_streak"]})

    if cycle_had_fetch_failure:
        health["fetch_failure_streak"] = health.get("fetch_failure_streak", 0) + 1
    else:
        health["fetch_failure_streak"] = 0
    if health["fetch_failure_streak"] == FETCH_FAILURE_STREAK_THRESHOLD:
        events.append({"rule": "fetch_failure_streak", "streak": health["fetch_failure_streak"]})

    return events
