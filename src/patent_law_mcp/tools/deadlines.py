"""특허 기간·기한·존속기간·연차료 계산기 (결정론적, 외부 API 불필요)

기간 계산은 특허법 제14조를 따릅니다.
1. 첫날은 넣지 않는다 (기산일 = 기준일 다음 날)
2. 월·연 단위는 역(曆)으로 계산: 기산일이 월 초가 아니면 마지막 달의 기산일 해당일 전날, 해당일이 없으면 그 달 말일
3. 마지막 날이 공휴일(토요일·일요일·근로자의 날 포함)이면 다음 날로 만료 — 절차 기한에만 적용 (존속기간 만료일에는 적용 안 함)
"""

import calendar
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional

import holidays
import yaml
from pydantic import Field

RULES_FILE = Path(__file__).parent.parent / "policies" / "patent_deadlines.yaml"

Preset = Literal["convention_priority", "domestic_priority", "pct_national_phase", "examination_request", "grace_period"]
RightType = Literal["patent", "utility_model"]


def _rules() -> Dict[str, Any]:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def period_end(base: date, months: int = 0, days: int = 0) -> date:
    """기준일(첫날 불산입)부터 months개월 또는 days일 되는 날 (공휴일 미반영)."""
    if bool(months) == bool(days):
        raise ValueError("개월 수와 일수 중 하나만 지정하십시오.")
    if days:
        return base + timedelta(days=days)
    start = base + timedelta(days=1)
    if start.day == 1:  # 월 초부터 기산하면 마지막 달의 말일
        last = _add_months(start, months - 1)
        return date(last.year, last.month, calendar.monthrange(last.year, last.month)[1])
    y, m = divmod(start.month - 1 + months, 12)
    year, month = start.year + y, m + 1
    if start.day > calendar.monthrange(year, month)[1]:  # 해당일이 없으면 그 달 말일
        return date(year, month, calendar.monthrange(year, month)[1])
    return date(year, month, start.day) - timedelta(days=1)


@lru_cache(maxsize=64)
def _kr_holidays(year: int) -> Dict[date, str]:
    days = dict(holidays.country_holidays("KR", years=year, language="ko"))
    days.setdefault(date(year, 5, 1), "근로자의 날")
    return days


def holiday_name(d: date, extra: frozenset = frozenset()) -> Optional[str]:
    if d in extra:
        return "추가 지정 휴일"
    if d.weekday() == 5:
        return "토요일"
    if d.weekday() == 6:
        return "일요일"
    return _kr_holidays(d.year).get(d)


def adjust_for_holidays(d: date, extra: frozenset = frozenset()) -> Dict[str, Any]:
    skipped = []
    while (name := holiday_name(d, extra)) is not None:
        skipped.append({"date": d.isoformat(), "reason": name})
        d += timedelta(days=1)
    return {"date": d, "skipped": skipped}


def calculate_patent_deadline(
    base_date: date,
    preset: Optional[Preset] = None,
    months: Annotated[Optional[int], Field(ge=1, le=600)] = None,
    days: Annotated[Optional[int], Field(ge=1, le=3650)] = None,
    extra_holidays: Optional[List[date]] = None,
) -> Dict[str, Any]:
    """특허 절차 기한을 특허법 제14조 방식(첫날 불산입, 역 계산, 공휴일이면 다음 날)으로 계산합니다.

    Args:
        base_date: 기준일 (출원일·우선일·공개일·통지서 송달일 등, YYYY-MM-DD)
        preset: 법정 기한 종류 ("convention_priority" 조약우선권 12개월, "domestic_priority" 국내우선권 12개월,
            "pct_national_phase" PCT 국내단계 31개월, "examination_request" 심사청구 3년, "grace_period" 공지예외 12개월)
        months: 직접 지정할 개월 수 (preset 대신)
        days: 직접 지정할 일수 (preset 대신, 예: 지정기간 30일)
        extra_holidays: 라이브러리에 없는 임시공휴일 등 추가 휴일
    """
    rules = _rules()
    info: Dict[str, Any] = {}
    if preset:
        if months or days:
            raise ValueError("preset과 months/days를 함께 지정할 수 없습니다.")
        p = rules["presets"][preset]
        months = p.get("months") or p.get("years", 0) * 12
        info = {"label": p["label"], "base": p["base"], "article": p["article"]}
    elif not (months or days):
        raise ValueError("preset, months, days 중 하나를 지정하십시오.")

    nominal = period_end(base_date, months=months or 0, days=days or 0)
    adjusted = adjust_for_holidays(nominal, frozenset(extra_holidays or []))
    return {
        **info,
        "base_date": base_date.isoformat(),
        "period": f"{months}개월" if months else f"{days}일",
        "nominal_end": nominal.isoformat(),
        "deadline": adjusted["date"].isoformat(),
        "shifted_for_holidays": adjusted["skipped"],
        "method": rules["metadata"]["basis"] + " — 첫날 불산입, 마지막 날이 공휴일(토요일·근로자의 날 포함)이면 다음 날",
        "unverified_items": [n for n in rules["verification_notes"] if "심사청구" in n] if preset == "examination_request" else [],
    }


def _term_end(application_date: date, right_type: str, extension_days: int) -> date:
    t = _rules()["term"]
    years = t["patent_years"] if right_type == "patent" else t["utility_model_years"]
    return period_end(application_date, months=years * 12) + timedelta(days=extension_days)


def calculate_patent_term(
    application_date: date,
    right_type: RightType = "patent",
    extension_days: Annotated[int, Field(ge=0, le=3650)] = 0,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """존속기간 만료일을 계산합니다 (특허: 출원일 후 20년이 되는 날, 실용신안: 10년).

    Args:
        application_date: 출원일 (PCT 국제출원은 국제출원일, 분할·변경출원은 원출원일)
        right_type: "patent" 또는 "utility_model"
        extension_days: 존속기간 연장 일수 (허가 등에 따른 연장·등록지연 연장이 등록된 경우)
        as_of: 기준일 (비우면 오늘)
    """
    t = _rules()["term"]
    today = as_of or date.today()
    end = _term_end(application_date, right_type, extension_days)
    remaining = (end - today).days
    return {
        "application_date": application_date.isoformat(),
        "right_type": "특허" if right_type == "patent" else "실용신안",
        "expiry_date": end.isoformat(),
        "extension_days": extension_days,
        "status_as_of": today.isoformat(),
        "is_expired_by_term": remaining < 0,
        "remaining_days": max(remaining, 0),
        "basis": (t["patent_article"] if right_type == "patent" else t["utility_model_article"])
        + (f", {t['extension_article']}" if extension_days else ""),
        "note": "존속기간 만료일은 공휴일이어도 미루지 않습니다. 연차료 미납 등으로 먼저 소멸할 수 있습니다.",
    }


def _anniversary(reg: date, years: int) -> date:
    return _add_months(reg, years * 12)


def calculate_annuity_schedule(
    registration_date: date,
    application_date: date,
    paid_through_year: Annotated[int, Field(ge=3, le=30)] = 3,
    right_type: RightType = "patent",
    extension_days: Annotated[int, Field(ge=0, le=3650)] = 0,
    as_of: Optional[date] = None,
    upcoming: Annotated[int, Field(ge=1, le=20)] = 5,
) -> Dict[str, Any]:
    """설정등록일 기준 연차료(4년차 이후) 납부기한, 추가납부기간, 회복 신청 가능기간과 현재 상태를 계산합니다.

    Args:
        registration_date: 설정등록일 (등록원부 기준. 등록공고일과 다를 수 있음)
        application_date: 출원일 (존속기간 만료 판정용)
        paid_through_year: 납부를 마친 마지막 연차 (설정등록 시 3년분 납부가 기본 → 3)
        right_type: "patent" 또는 "utility_model"
        extension_days: 존속기간 연장 일수
        as_of: 기준일 (비우면 오늘)
        upcoming: 표시할 향후 납부 연차 수
    """
    if registration_date < application_date:
        raise ValueError("설정등록일이 출원일보다 빠를 수 없습니다.")
    a = _rules()["annuity"]
    today = as_of or date.today()
    expiry = _term_end(application_date, right_type, extension_days)

    schedule = []
    year = paid_through_year + 1
    while len(schedule) < upcoming:
        due = _anniversary(registration_date, year - 1)
        if due > expiry:
            break
        # 추가납부기간 만료일(공휴일 반영)부터 회복 신청 기간을 센다
        late_end = adjust_for_holidays(period_end(due, months=a["late_payment_months"]))["date"]
        schedule.append({
            "year": year,
            "due_date": due.isoformat(),
            "due_date_if_holiday_shifted": adjust_for_holidays(due)["date"].isoformat(),
            "late_payment_until": late_end.isoformat(),
            "restoration_until": period_end(late_end, months=a["restoration_months"]).isoformat(),
        })
        year += 1

    if not schedule:
        status = "더 낼 연차료 없음 (존속기간 만료까지 납부 완료)"
    else:
        nxt = schedule[0]
        if today <= date.fromisoformat(nxt["due_date_if_holiday_shifted"]):
            status = f"정상 — 다음 납부: {nxt['year']}년차분, 기한 {nxt['due_date']}"
        elif today <= date.fromisoformat(nxt["late_payment_until"]):
            status = f"추가납부기간 — {nxt['year']}년차분을 {nxt['late_payment_until']}까지 가산금과 함께 납부해야 함 ({a['late_article']})"
        elif today <= date.fromisoformat(nxt["restoration_until"]):
            status = f"추가납부기간 경과 — {nxt['restoration_until']}까지 회복 신청 가능 여부 확인 ({a['restoration_article']}, 원문 확인 필요)"
        else:
            status = "연차료 미납으로 소멸했을 가능성이 큼 — 등록원부로 확인하십시오"

    return {
        "registration_date": registration_date.isoformat(),
        "expiry_date": expiry.isoformat(),
        "paid_through_year": paid_through_year,
        "status_as_of": today.isoformat(),
        "status": status,
        "schedule": schedule,
        "basis": f"{a['due_article']} (4년차부터 매년 설정등록일 해당일 기준 납부), {a['late_article']} (6개월 추가납부)",
        "unverified_items": [n for n in _rules()["verification_notes"] if "연차료" in n],
        "note": "납부 금액은 계산하지 않습니다 (특허료 등의 징수규칙 확인). 실제 납부 이력은 등록원부로 확인하십시오.",
    }


def check_patent_rights_status(
    patent_identifier: Annotated[str, Field(min_length=5, max_length=40)],
    number_type: Literal["auto", "application", "registration", "publication"] = "auto",
    registration_date: Optional[date] = None,
    paid_through_year: Annotated[Optional[int], Field(ge=3, le=30)] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """특허번호로 서지·상태를 조회(번호 검증)한 뒤 존속기간 만료일과, 설정등록일·납부 연차를 주면 연차료 상태까지 정리합니다.

    Args:
        patent_identifier: 특허번호 (등록번호 권장. 출원번호는 KIPRIS_API_KEY 필요)
        number_type: 번호 종류
        registration_date: 설정등록일 (KIPRIS 조회 결과에 있으면 생략 가능)
        paid_through_year: 납부를 마친 마지막 연차 (주면 연차료 상태 계산)
        as_of: 기준일 (비우면 오늘)
    """
    from patent_law_mcp.tools.kipris_connector import fetch_patent_smart

    patent = fetch_patent_smart(patent_identifier, number_type)
    if not patent["found"]:
        return patent

    def parse(d: str) -> Optional[date]:
        digits = "".join(ch for ch in d or "" if ch.isdigit())
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8])) if len(digits) >= 8 else None

    app_date = parse(patent.get("application_date", ""))
    reg_date = registration_date or parse(patent.get("register_date", ""))
    result: Dict[str, Any] = {
        "patent": {k: patent.get(k) for k in ("title", "applicant", "application_number", "register_number", "source")},
        "reported_status": patent.get("register_status") or "미확인",
        "events": patent.get("events", []),
    }
    if app_date:
        result["term"] = calculate_patent_term(app_date, as_of=as_of)
    else:
        result["term"] = {"error": "출원일을 확인하지 못해 존속기간을 계산하지 않았습니다."}

    if app_date and reg_date and paid_through_year is not None:
        result["annuity"] = calculate_annuity_schedule(reg_date, app_date, paid_through_year, as_of=as_of)
    elif paid_through_year is not None and not reg_date:
        result["annuity"] = {"error": "설정등록일(registration_date)을 입력하십시오. Google Patents의 'granted' 일자는 등록공고일일 수 있습니다."}
    else:
        result["annuity"] = {"note": "registration_date와 paid_through_year를 주면 연차료 납부기한·상태를 계산합니다."}
    result["note"] = "권리 상태의 최종 확인은 특허청 등록원부로 하십시오."
    return result
