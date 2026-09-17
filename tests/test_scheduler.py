from datetime import date, datetime, timedelta

from src.scheduler import is_burst_active, scan_dates, start_burst


def test_burst_active_before_deadline_and_inactive_after():
    now = datetime(2026, 9, 18, 12, 0)
    burst_until = datetime(2026, 9, 18, 12, 30)

    assert is_burst_active(now, burst_until) is True
    assert is_burst_active(datetime(2026, 9, 18, 12, 31), burst_until) is False
    assert is_burst_active(now, None) is False


def test_start_burst_sets_30_minute_window():
    now = datetime(2026, 9, 18, 12, 0)

    assert start_burst(now) == now + timedelta(minutes=30)


def test_baseline_scan_range_is_horizon_minus2_to_plus3():
    today = date(2026, 9, 18)
    horizon = date(2026, 9, 22)

    dates = scan_dates("baseline", today, horizon)

    assert dates == ["20260920", "20260921", "20260922", "20260923", "20260924", "20260925"]


def test_baseline_scan_range_never_goes_before_today():
    today = date(2026, 9, 18)
    horizon = date(2026, 9, 18)

    dates = scan_dates("baseline", today, horizon)

    assert dates[0] == "20260918"


def test_burst_scan_range_is_wider_than_baseline():
    today = date(2026, 9, 18)
    horizon = date(2026, 9, 22)

    dates = scan_dates("burst", today, horizon)

    assert dates == [
        "20260921", "20260922", "20260923", "20260924", "20260925", "20260926", "20260927",
    ]


def test_full_scan_covers_35_days_from_today():
    today = date(2026, 9, 18)

    dates = scan_dates("full_scan", today, horizon=None)

    assert dates[0] == "20260918"
    assert dates[-1] == "20261023"
    assert len(dates) == 36
