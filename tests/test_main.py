from datetime import datetime

from src.main import determine_mode, merge_showtimes, showtime_to_dict
from src.parser import Showtime


def make_showtime(date, key):
    return Showtime(
        date=date,
        start_time="10:00",
        start_datetime=datetime.strptime(f"{date} 10:00", "%Y-%m-%d %H:%M"),
        screen_no="018",
        screen_name="IMAX관",
        movie_title="오디세이",
        product_name="오디세이(IMAX LASER 2D)",
        seats_remaining=10,
        seats_total=624,
        key=key,
    )


def test_forced_full_scan_overrides_burst_state():
    now = datetime(2026, 9, 18, 12, 0)
    assert determine_mode("full_scan", "2026-09-18T12:30:00", now) == "full_scan"


def test_auto_mode_is_burst_while_burst_until_in_future():
    now = datetime(2026, 9, 18, 12, 0)
    assert determine_mode(None, "2026-09-18T12:30:00", now) == "burst"


def test_auto_mode_falls_back_to_baseline_after_burst_expires():
    now = datetime(2026, 9, 18, 12, 31)
    assert determine_mode(None, "2026-09-18T12:30:00", now) == "baseline"


def test_auto_mode_is_baseline_with_no_burst_state():
    now = datetime(2026, 9, 18, 12, 0)
    assert determine_mode(None, None, now) == "baseline"


def test_merge_keeps_untouched_dates_and_replaces_scanned_dates():
    previous = [showtime_to_dict(make_showtime("2026-09-22", "20260922|1000|018"))]
    fresh = [make_showtime("2026-09-20", "20260920|1000|018")]

    merged = merge_showtimes(previous, scanned_dates_iso={"2026-09-20"}, fresh=fresh)

    dates = sorted(s.date for s in merged)
    assert dates == ["2026-09-20", "2026-09-22"]


def test_merge_replaces_stale_entry_for_rescanned_date():
    stale = showtime_to_dict(make_showtime("2026-09-20", "20260920|1000|018"))
    stale["seats_remaining"] = 0
    fresh = [make_showtime("2026-09-20", "20260920|1000|018")]  # seats_remaining=10

    merged = merge_showtimes([stale], scanned_dates_iso={"2026-09-20"}, fresh=fresh)

    assert len(merged) == 1
    assert merged[0].seats_remaining == 10
