from dataclasses import dataclass
from datetime import datetime, timedelta

SITE_NO = "0013"
SCREEN_NO_IMAX = "018"


@dataclass(frozen=True)
class Showtime:
    date: str
    start_time: str
    start_datetime: datetime
    screen_no: str
    screen_name: str
    movie_title: str
    product_name: str
    seats_remaining: int
    seats_total: int
    key: str


def _shift_overflow_time(scn_ymd: str, hhmm: str) -> tuple[str, datetime]:
    """CGV는 익일 새벽 상영을 '2500' 같은 24시 초과 값으로 표기한다 (CLAUDE.md 참조)."""
    base_date = datetime.strptime(scn_ymd, "%Y%m%d").date()
    hour, minute = int(hhmm[:2]), int(hhmm[2:])
    day_shift, hour = divmod(hour, 24)
    shifted_date = base_date + timedelta(days=day_shift)
    start_time = f"{hour:02d}:{minute:02d}"
    start_datetime = datetime(shifted_date.year, shifted_date.month, shifted_date.day, hour, minute)
    return start_time, start_datetime


def parse_showtimes(response: dict) -> list[Showtime]:
    if response.get("statusCode") != 0:
        raise ValueError(f"unexpected statusCode: {response.get('statusCode')}")

    showtimes = []
    for rec in response.get("data", []):
        if rec["siteNo"] != SITE_NO or rec["scnsNo"] != SCREEN_NO_IMAX:
            continue

        scn_ymd = rec["scnYmd"]
        start_time, start_datetime = _shift_overflow_time(scn_ymd, rec["scnsrtTm"])
        raw_date = datetime.strptime(scn_ymd, "%Y%m%d").date().isoformat()

        showtimes.append(
            Showtime(
                date=raw_date,
                start_time=start_time,
                start_datetime=start_datetime,
                screen_no=rec["scnsNo"],
                screen_name=rec["scnsNm"],
                movie_title=rec["movNm"],
                product_name=rec["prodNm"],
                seats_remaining=int(rec["frSeatCnt"]),
                seats_total=int(rec["stcnt"]),
                key=f"{scn_ymd}|{rec['scnsrtTm']}|{rec['scnsNo']}",
            )
        )
    return showtimes
