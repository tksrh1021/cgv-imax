import json
import os
from datetime import datetime

from src.parser import parse_showtimes

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def load_sample(name):
    with open(os.path.join(SAMPLES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def test_midnight_overflow_time_shifts_to_next_day():
    # 실제 응답(2026-09-18)의 IMAX 018 회차 중 scnsrtTm=2500 레코드가 존재함 (CLAUDE.md 참조)
    response = load_sample("searchSchByMov_nocustno_raw.json")
    showtimes = parse_showtimes(response)

    midnight_showtime = next(s for s in showtimes if s.date == "2026-09-18" and s.start_time == "01:00")

    assert midnight_showtime.start_datetime == datetime(2026, 9, 19, 1, 0)
    assert midnight_showtime.screen_no == "018"


def test_real_response_only_yields_target_theater_and_screen():
    response = load_sample("searchSchByMov_nocustno_raw.json")
    showtimes = parse_showtimes(response)

    assert len(showtimes) > 0
    assert all(s.screen_no == "018" and s.screen_name == "IMAX관" for s in showtimes)


def test_excludes_p013_even_when_it_has_an_imax_screen_code():
    # 실제 데이터에는 P013(씨네드쉐프 용산)에 IMAX 편성이 없으므로, siteNo 필터가
    # scnsNo 필터에 가려 검증되지 않는 걸 막기 위해 합성 레코드로 직접 확인한다.
    response = {
        "statusCode": 0,
        "statusMessage": "조회 되었습니다.",
        "data": [
            {
                "siteNo": "0013",
                "scnsNo": "018",
                "scnsNm": "IMAX관",
                "scnYmd": "20260920",
                "scnsrtTm": "1000",
                "scnendTm": "1300",
                "frSeatCnt": "10",
                "stcnt": "624",
                "movNm": "오디세이",
                "prodNm": "오디세이(IMAX LASER 2D)",
            },
            {
                "siteNo": "P013",
                "scnsNo": "018",
                "scnsNm": "IMAX관",
                "scnYmd": "20260920",
                "scnsrtTm": "1000",
                "scnendTm": "1300",
                "frSeatCnt": "10",
                "stcnt": "624",
                "movNm": "오디세이",
                "prodNm": "오디세이(IMAX LASER 2D)",
            },
        ],
    }

    showtimes = parse_showtimes(response)

    assert len(showtimes) == 1
    assert showtimes[0].key.split("|")[0] == "20260920"
