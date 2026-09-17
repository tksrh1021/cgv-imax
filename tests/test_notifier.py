from datetime import datetime, timedelta

from src import notifier


def test_overlapping_burst_jobs_do_not_double_notify(monkeypatch):
    """burst 모드에서 job이 겹쳐 실행돼도, 두 job이 같은 notified_state(커밋된 state 파일)를
    공유하는 한 동일 이벤트에 대해 텔레그램 발송은 1회만 일어나야 한다."""
    sent = []
    monkeypatch.setattr(notifier, "send_message", lambda text: sent.append(text))

    event = {"rule": "booking_horizon_extended", "previous_horizon": "2026-09-18", "new_horizon": "2026-09-22"}
    shared_notified_state = {}

    # job A가 먼저 처리하고 state에 기록
    notifier.notify_events([event], shared_notified_state, datetime(2026, 9, 18, 15, 0, 0))
    # 5초 뒤 겹쳐 기동된 job B가 같은 이벤트를 같은 state로 재처리
    notifier.notify_events([event], shared_notified_state, datetime(2026, 9, 18, 15, 0, 5))

    assert len(sent) == 1


def test_new_showtime_dedup_uses_showtime_keys_not_object_identity(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier, "send_message", lambda text: sent.append(text))

    class FakeShowtime:
        def __init__(self, key):
            self.key = key
            self.date = "2026-09-20"
            self.start_time = "10:00"
            self.screen_name = "IMAX관"
            self.seats_remaining = 10
            self.seats_total = 624

    event_a = {"rule": "new_showtime", "new_showtimes": [FakeShowtime("20260920|1000|018")]}
    event_b = {"rule": "new_showtime", "new_showtimes": [FakeShowtime("20260920|1000|018")]}  # 다른 객체, 같은 회차
    state = {}

    notifier.notify_events([event_a], state, datetime(2026, 9, 18, 15, 0, 0))
    notifier.notify_events([event_b], state, datetime(2026, 9, 18, 15, 0, 5))

    assert len(sent) == 1


def test_cancellation_seat_is_throttled_within_10_minutes(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier, "send_message", lambda text: sent.append(text))

    class FakeShowtime:
        key = "20260920|1000|018"
        date = "2026-09-20"
        start_time = "10:00"
        screen_name = "IMAX관"
        seats_remaining = 1
        seats_total = 624

    event = {"rule": "cancellation_seat", "showtime": FakeShowtime()}
    state = {}
    base = datetime(2026, 9, 18, 15, 0, 0)

    notifier.notify_events([event], state, base)
    notifier.notify_events([event], state, base + timedelta(minutes=5))  # 10분 이내 → 억제
    notifier.notify_events([event], state, base + timedelta(minutes=11))  # 10분 경과 → 재발송

    assert len(sent) == 2
