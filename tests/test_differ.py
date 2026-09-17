from datetime import datetime

from src.differ import diff_snapshot, update_health_streaks
from src.parser import Showtime


def make_showtime(date, start_time="10:00", screen_no="018", seats_remaining=10, key=None):
    return Showtime(
        date=date,
        start_time=start_time,
        start_datetime=datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M"),
        screen_no=screen_no,
        screen_name="IMAX관",
        movie_title="오디세이",
        product_name="오디세이(IMAX LASER 2D)",
        seats_remaining=seats_remaining,
        seats_total=624,
        key=key or f"{date.replace('-', '')}|{start_time.replace(':', '')}|{screen_no}",
    )


def test_first_run_without_snapshot_produces_no_events():
    current = [make_showtime("2026-09-18")]

    result = diff_snapshot(None, current)

    assert result.events == []
    assert result.horizon == "2026-09-18"


def test_horizon_extension_is_detected():
    previous = {
        "horizon": "2026-09-18",
        "showtimes": [
            {"key": "20260918|1000|018", "seats_remaining": 10},
        ],
    }
    current = [
        make_showtime("2026-09-18"),
        make_showtime("2026-09-22", key="20260922|1000|018"),
    ]

    result = diff_snapshot(previous, current)

    assert result.horizon == "2026-09-22"
    horizon_events = [e for e in result.events if e["rule"] == "booking_horizon_extended"]
    assert len(horizon_events) == 1
    assert horizon_events[0]["previous_horizon"] == "2026-09-18"
    assert horizon_events[0]["new_horizon"] == "2026-09-22"


def test_new_showtime_is_detected_without_horizon_change():
    previous = {
        "horizon": "2026-09-18",
        "showtimes": [
            {"key": "20260918|1000|018", "seats_remaining": 10},
        ],
    }
    current = [
        make_showtime("2026-09-18"),
        make_showtime("2026-09-18", start_time="14:00", key="20260918|1400|018"),
    ]

    result = diff_snapshot(previous, current)

    assert not any(e["rule"] == "booking_horizon_extended" for e in result.events)
    new_showtime_events = [e for e in result.events if e["rule"] == "new_showtime"]
    assert len(new_showtime_events) == 1
    assert [s.key for s in new_showtime_events[0]["new_showtimes"]] == ["20260918|1400|018"]


def test_cancellation_seat_detected_on_zero_to_nonzero_transition():
    previous = {
        "horizon": "2026-09-18",
        "showtimes": [
            {"key": "20260918|1000|018", "seats_remaining": 0},
        ],
    }
    current = [make_showtime("2026-09-18", seats_remaining=1)]

    result = diff_snapshot(previous, current)

    cancellation_events = [e for e in result.events if e["rule"] == "cancellation_seat"]
    assert len(cancellation_events) == 1
    assert cancellation_events[0]["showtime"].key == "20260918|1000|018"


def test_zero_result_streak_fires_exactly_once_at_threshold():
    health = {}
    events_per_cycle = [
        update_health_streaks(health, cycle_had_zero_result=True, cycle_had_fetch_failure=False) for _ in range(7)
    ]

    fired_at = [i for i, events in enumerate(events_per_cycle, start=1) if events]
    assert fired_at == [5]
    assert events_per_cycle[4] == [{"rule": "silent_zero_result", "streak": 5}]


def test_streak_resets_on_success():
    health = {"zero_result_streak": 4, "fetch_failure_streak": 3}

    events = update_health_streaks(health, cycle_had_zero_result=False, cycle_had_fetch_failure=False)

    assert events == []
    assert health["zero_result_streak"] == 0
    assert health["fetch_failure_streak"] == 0


def test_fetch_failure_streak_fires_exactly_once_at_threshold():
    health = {}
    events_per_cycle = [
        update_health_streaks(health, cycle_had_zero_result=False, cycle_had_fetch_failure=True) for _ in range(6)
    ]

    fired_at = [i for i, events in enumerate(events_per_cycle, start=1) if events]
    assert fired_at == [5]
