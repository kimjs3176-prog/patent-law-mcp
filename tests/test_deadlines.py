from datetime import date

import pytest

from patent_law_mcp.tools.deadlines import (
    adjust_for_holidays,
    calculate_annuity_schedule,
    calculate_patent_deadline,
    calculate_patent_term,
    check_patent_rights_status,
    period_end,
)
from conftest import fixture_text


@pytest.mark.parametrize(
    "base,months,expected",
    [
        (date(2024, 3, 15), 12, date(2025, 3, 15)),   # 기산일 3/16 → 다음 해 3/16의 전날
        (date(2024, 1, 30), 1, date(2024, 2, 29)),    # 기산일 1/31, 2월에 31일 없음 → 말일
        (date(2024, 12, 31), 2, date(2025, 2, 28)),   # 기산일 1/1(월 초) → 마지막 달 말일
        (date(2010, 6, 30), 240, date(2030, 6, 30)),  # 출원일 후 20년
    ],
)
def test_period_end_months(base, months, expected):
    assert period_end(base, months=months) == expected


def test_period_end_days():
    assert period_end(date(2025, 1, 1), days=30) == date(2025, 1, 31)
    with pytest.raises(ValueError):
        period_end(date(2025, 1, 1), months=1, days=1)


def test_holiday_shift_includes_saturday_lunar_and_labor_day():
    r = adjust_for_holidays(date(2025, 1, 25))  # 토 → 일 → 1/27 임시공휴일 → 설 연휴 1/28~30
    assert r["date"] == date(2025, 1, 31)
    assert [s["reason"] for s in r["skipped"]][:2] == ["토요일", "일요일"]
    assert adjust_for_holidays(date(2025, 5, 1))["date"] == date(2025, 5, 2)  # 근로자의 날


def test_priority_preset():
    r = calculate_patent_deadline(date(2024, 10, 3), preset="convention_priority")
    assert r["nominal_end"] == "2025-10-03"   # 개천절
    assert r["deadline"] == "2025-10-10"      # 10/3 개천절, 10/4~5 주말, 10/6~8 추석, 10/9 한글날
    assert r["article"] == "특허법 제54조"


def test_pct_and_custom_days():
    assert calculate_patent_deadline(date(2023, 1, 16), preset="pct_national_phase")["nominal_end"] == "2025-08-16"
    assert calculate_patent_deadline(date(2025, 3, 3), days=30)["nominal_end"] == "2025-04-02"
    with pytest.raises(ValueError):
        calculate_patent_deadline(date(2025, 3, 3))


def test_patent_term():
    r = calculate_patent_term(date(2010, 6, 30), as_of=date(2026, 11, 8))
    assert r["expiry_date"] == "2030-06-30" and not r["is_expired_by_term"]
    assert calculate_patent_term(date(2010, 6, 30), "utility_model", as_of=date(2026, 11, 8))["is_expired_by_term"]
    assert calculate_patent_term(date(2010, 6, 30), extension_days=100)["expiry_date"] == "2030-10-08"


def test_annuity_schedule_and_status():
    reg, app = date(2011, 9, 28), date(2010, 6, 30)
    r = calculate_annuity_schedule(reg, app, paid_through_year=3, as_of=date(2014, 9, 1))
    assert r["schedule"][0] == {
        "year": 4,
        "due_date": "2014-09-28",
        "due_date_if_holiday_shifted": "2014-09-29",
        "late_payment_until": "2015-03-30",
        "restoration_until": "2015-06-30",
    }
    assert r["status"].startswith("정상")
    assert calculate_annuity_schedule(reg, app, 3, as_of=date(2014, 12, 1))["status"].startswith("추가납부기간")
    assert calculate_annuity_schedule(reg, app, 3, as_of=date(2015, 5, 1))["status"].startswith("추가납부기간 경과")
    assert calculate_annuity_schedule(reg, app, 3, as_of=date(2016, 1, 1))["status"].startswith("연차료 미납")


def test_annuity_stops_at_term_expiry():
    r = calculate_annuity_schedule(date(2011, 9, 28), date(2010, 6, 30), paid_through_year=18, upcoming=10)
    assert [s["year"] for s in r["schedule"]] == [19]  # 20년차 기한(2030-09-28)은 만료일(2030-06-30) 뒤
    done = calculate_annuity_schedule(date(2011, 9, 28), date(2010, 6, 30), paid_through_year=19)
    assert done["schedule"] == [] and done["status"].startswith("더 낼 연차료 없음")


def test_rights_status_uses_verified_fetch(fake_http):
    fake_http.routes["KR101070281B1"] = (200, fixture_text("google_registration.html"))
    r = check_patent_rights_status("10-1070281", as_of=date(2026, 11, 8))
    assert r["term"]["expiry_date"] == "2028-11-28"
    assert "registration_date" in r["annuity"]["note"]
    r = check_patent_rights_status("10-1070281", registration_date=date(2011, 10, 6), paid_through_year=15, as_of=date(2026, 11, 8))
    assert r["annuity"]["schedule"][0]["year"] == 16
