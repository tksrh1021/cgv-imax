import pytest

from src import fetcher


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_403_raises_access_denied(monkeypatch):
    monkeypatch.setattr(fetcher.httpx, "get", lambda *a, **k: FakeResponse(403))

    with pytest.raises(fetcher.AccessDenied):
        fetcher.fetch_schedule("20260918")


def test_429_raises_access_denied(monkeypatch):
    monkeypatch.setattr(fetcher.httpx, "get", lambda *a, **k: FakeResponse(429))

    with pytest.raises(fetcher.AccessDenied):
        fetcher.fetch_schedule("20260918")


def test_non_zero_status_code_raises_fetch_error(monkeypatch):
    monkeypatch.setattr(
        fetcher.httpx,
        "get",
        lambda *a, **k: FakeResponse(200, {"statusCode": 400, "statusMessage": "발매통제범위코드는 필수 요청 파라미터 입니다."}),
    )

    with pytest.raises(fetcher.FetchError):
        fetcher.fetch_schedule("20260918")


def test_successful_response_returns_data(monkeypatch):
    payload = {"statusCode": 0, "statusMessage": "조회 되었습니다.", "data": []}
    monkeypatch.setattr(fetcher.httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    assert fetcher.fetch_schedule("20260918") == payload
