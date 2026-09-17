import httpx

BASE_URL = "https://cgv.co.kr/api/v1/booking/searchSchByMov"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class AccessDenied(Exception):
    """403/429 — CGV의 명시적 거부. 재시도하지 않는다 (CLAUDE.md / detection_rules.access_denied)."""


class FetchError(Exception):
    """네트워크 오류 또는 예상 밖의 응답. fetch_failure_streak 판단용."""


def fetch_schedule(scn_ymd: str, *, site_no: str = "0013", mov_no: str = "30001323", timeout: float = 10.0) -> dict:
    params = {
        "coCd": "A420",
        "siteNo": site_no,
        "scnYmd": scn_ymd,
        "movNo": mov_no,
        "rtctlScopCd": "08",
    }
    headers = {
        "Accept": "application/json",
        "Referer": "https://cgv.co.kr/",
        "User-Agent": USER_AGENT,
    }

    try:
        response = httpx.get(BASE_URL, params=params, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise FetchError(str(exc)) from exc

    if response.status_code in (403, 429):
        raise AccessDenied(f"HTTP {response.status_code}")
    if response.status_code != 200:
        raise FetchError(f"HTTP {response.status_code}")

    data = response.json()
    if data.get("statusCode") != 0:
        raise FetchError(f"statusCode={data.get('statusCode')}: {data.get('statusMessage')}")
    return data
