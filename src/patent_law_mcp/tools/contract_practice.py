"""국유특허 기술실시계약 실무 도구

- design_licensing_terms: 통상·전용실시 계약조건 초안 (기준값은 정책 YAML에서 읽음)
- review_licensing_contract: 계약서 초안의 필수 조항 1차 점검 (부정·면제 문구 인식)
"""

import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence

from pydantic import Field

from patent_law_mcp.policies.policy_manager import ProfileName, policy_for

LicenseType = Literal["non_exclusive", "exclusive"]
CompanyScale = Literal["farmer", "sme", "middle", "large"]


def require_choice(value: str, allowed: Sequence[str], name: str) -> str:
    """MCP 밖에서 직접 호출될 때도 허용값을 강제합니다 (예: '전용실시'를 조용히 통상실시로 처리하지 않도록)."""
    if value not in allowed:
        raise ValueError(f"{name}은(는) {', '.join(allowed)} 중 하나여야 합니다 (입력: {value!r}).")
    return value


def design_licensing_terms(
    patent_id: str,
    license_type: LicenseType = "non_exclusive",
    company_scale: CompanyScale = "sme",
    target_territory: str = "대한민국",
    contract_period_years: Annotated[int, Field(ge=1, le=20)] = 3,
    expected_sales_annual: Annotated[Optional[int], Field(ge=0)] = None,
    profile: Optional[ProfileName] = None,
) -> Dict[str, Any]:
    """기술실시계약 조건 초안을 산출합니다 (국유특허는 최소실시료·경쟁입찰 등 고시·규정 기준 반영).

    Args:
        patent_id: 대상 특허번호
        license_type: "non_exclusive"(통상실시) 또는 "exclusive"(전용실시)
        company_scale: "farmer"(농어업인), "sme"(중소기업), "middle"(중견기업), "large"(대기업)
        target_territory: 실시 지역
        contract_period_years: 계약 기간(년)
        expected_sales_annual: 실시 제품 예상 연매출(원). 주면 연간 경상기술료를 추정합니다
        profile: "national"(국유특허), "public_research"(대학·출연연), "private_company"(민간). 비우면 기본 프로파일
    """
    require_choice(license_type, ("non_exclusive", "exclusive"), "license_type")
    require_choice(company_scale, ("farmer", "sme", "middle", "large"), "company_scale")
    if not 1 <= contract_period_years <= 20:
        raise ValueError("contract_period_years는 1~20년이어야 합니다.")
    if expected_sales_annual is not None and expected_sales_annual < 0:
        raise ValueError("expected_sales_annual은 0 이상이어야 합니다.")

    is_exclusive = license_type == "exclusive"
    pm = policy_for(profile)
    national = pm.is_national
    art = pm.articles
    practice = pm.section("contract_practice")
    rate = practice["reference_rates_by_scale"][company_scale]
    excl = pm.section("exclusive_licensing") if national else {}
    min_royalty = excl.get("minimum_royalty_amount", 0)
    deadline = excl.get("payment_deadline_days")
    lump_sum = rate["lump_sum"] * (practice["exclusive_lump_sum_multiplier"] if is_exclusive else 1)
    running_rate = rate["running_rate"] * (practice["exclusive_running_multiplier"] if is_exclusive else 1)
    if national and is_exclusive and lump_sum < min_royalty:
        lump_sum = min_royalty

    financial: Dict[str, Any] = {
        "lump_sum_fee_krw": int(lump_sum),
        "lump_sum_payment": f"계약 체결일부터 {deadline}일 이내 납부" if national and is_exclusive else "계약서에서 납부 기한 지정",
        "running_royalty_rate": f"실시 제품 순매출액의 {running_rate * 100:.2f}%",
        "rate_basis": f"{rate['description']} — 기관 내부 참고 요율이며 법정 요율이 아닙니다",
        "minimum_royalty_rule": (
            f"전용실시 최소실시료 {min_royalty:,}원 이상, 계약일부터 {deadline}일 이내 납부 ({art['exclusive_minimum_royalty']})"
            if national and is_exclusive
            else ("해당 없음 (통상실시)" if national else "해당 없음 (국유특허 고시 기준은 이 프로파일에 적용되지 않음)")
        ),
    }
    if expected_sales_annual is not None:
        financial["estimated_annual_running_royalty_krw"] = int(round(expected_sales_annual * running_rate))
        financial["estimate_basis"] = f"예상 연매출 {expected_sales_annual:,}원 × {running_rate * 100:.2f}%"

    procedures: List[str] = []
    if not national:
        procedures.append(f"{pm.metadata['notice_name']}에 따른 내부 심의·승인 절차를 거치십시오 ({pm.metadata['parent_regulation']}).")
        if is_exclusive:
            procedures.append(f"전용실시권은 등록해야 효력이 생깁니다 ({art['exclusive_license_registration']}). 등록비용 부담 주체를 명시하십시오.")
    elif is_exclusive:
        if excl["competitive_bidding_required"]:
            procedures.append(
                f"전용실시권 설정은 경쟁입찰이 원칙입니다 ({art['exclusive_competitive_bidding']}). "
                "수의계약은 같은 항 단서 각 호의 사유에 해당할 때만 가능합니다."
            )
        procedures.append(f"전용실시권은 등록해야 효력이 생깁니다 ({art['exclusive_license_registration']}). 등록비용 부담 주체를 명시하십시오.")
    else:
        procedures.append(f"통상실시권 허락은 수의계약으로 합니다 ({art['non_exclusive_private_contract']}).")
    if national and company_scale == "farmer":
        procedures.append(f"농어업인 소득 증대 목적이면 무상 처분 사유({art['free_disposal_grounds']}) 해당 여부를 먼저 검토하십시오.")

    clauses = [
        {
            "clause": "불실시 해지특약",
            "detail": f"계약일부터 {practice['due_diligence_years']}년 이내에 정당한 사유 없이 사업화에 착수하지 않으면 해지할 수 있음",
            "basis": "기관 실무 기준",
        },
        {
            "clause": "재실시권(Sub-license) 제한",
            "detail": "실시권자는 사전 서면 승인 없이 제3자에게 재실시권을 설정하거나 실시권을 양도할 수 없음",
            "basis": "기관 실무 기준",
        },
        {
            "clause": "매출 보고 및 장부 열람",
            "detail": f"매 사업연도 종료 후 {practice['sales_report_deadline_days']}일 이내 매출 보고, 관리기관의 장부 열람 요구권",
            "basis": "기관 실무 기준 (경상기술료 정산·감사 대비)",
        },
    ]
    if national and is_exclusive:
        renewal = pm.section("exclusive_renewal")
        clauses.insert(0, {
            "clause": "전용실시 최소실시료 납부",
            "detail": f"실시료의 일부로 {min_royalty:,}원 이상을 계약일부터 {deadline}일 이내 납부",
            "basis": art["exclusive_minimum_royalty"],
        })
        clauses.append({
            "clause": "갱신 신청 기한",
            "detail": f"갱신을 원하면 만료 {renewal['application_deadline_days_before_expiry']}일 전까지 사유 증빙과 함께 신청",
            "basis": art["exclusive_renewal"],
        })

    if national and is_exclusive:
        financial["private_contract_exceptions"] = excl["private_contract_exceptions"]
    return {
        "patent_id": patent_id,
        "license_structure": {
            "type": "전용실시권 (Exclusive License)" if is_exclusive else "통상실시권 (Non-exclusive License)",
            "contract_period": f"{contract_period_years}년",
            "territory": target_territory,
            "field_of_use": "계약서에 지정 (전 산업 분야 또는 지정 제품군)",
        },
        "financial_terms": financial,
        "required_procedures": procedures,
        "mandatory_practice_clauses": clauses,
        "legal_audit_basis": pm.audit_block(),
    }


# ---------------------------------------------------------------- 계약서 검토
_AMOUNT_RE = re.compile(r"(\d[\d,]*)\s*(억|천만|백만|만)?\s*원")
_UNIT = {None: 1, "만": 10_000, "백만": 1_000_000, "천만": 10_000_000, "억": 100_000_000}
_DAYS_RE = re.compile(r"(\d+)\s*일\s*(?:이내|안에|까지)")


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.。])\s+|\n+|(?=[①②③④⑤⑥⑦⑧⑨⑩])", text)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p and p.strip()]


def _hits(sentences: List[str], pattern: str) -> List[str]:
    return [s for s in sentences if re.search(pattern, s)]


def _item(item: str, status: str, comment: str, evidence: Optional[str] = None) -> Dict[str, Any]:
    out = {"item": item, "status": status, "comment": comment}
    if evidence:
        out["evidence"] = evidence[:160]
    return out


def _amounts(sentence: str) -> List[int]:
    return [int(m.group(1).replace(",", "")) * _UNIT[m.group(2)] for m in _AMOUNT_RE.finditer(sentence)]


def review_licensing_contract(
    contract_text: str,
    license_type: LicenseType = "exclusive",
    profile: Optional[ProfileName] = None,
) -> Dict[str, Any]:
    """기술실시계약서 초안에서 필수 조항의 존재와 부정·면제 문구를 1차 점검합니다.

    상태: PASS(조항 확인) · WARNING(조항 없음) · REVIEW(부정·면제·금액 미기재 등 사람 확인 필요) · FAIL(기준 위반 확인).
    문장 단위 키워드 점검이므로 최종 판단은 법무 검토로 하십시오.

    Args:
        contract_text: 계약서 초안 본문
        license_type: "exclusive"(전용실시) 또는 "non_exclusive"(통상실시)
        profile: "national"(국유특허, 최소실시료 점검 포함), "public_research", "private_company". 비우면 기본 프로파일
    """
    require_choice(license_type, ("non_exclusive", "exclusive"), "license_type")
    is_exclusive = license_type == "exclusive"
    pm = policy_for(profile)
    art = pm.articles
    practice = pm.section("contract_practice")
    sents = _sentences(contract_text)
    checklist: List[Dict[str, Any]] = []

    if is_exclusive and pm.is_national:
        excl = pm.section("exclusive_licensing")
        min_royalty, deadline = excl["minimum_royalty_amount"], excl["payment_deadline_days"]
        name = f"전용실시 최소실시료 {min_royalty:,}원 이상·{deadline}일 이내 납부 ({art['exclusive_minimum_royalty']})"
        hits = _hits(sents, r"최소\s*실시료|선급\s*(?:기술료|실시료)|계약금")
        if not hits:
            checklist.append(_item(name, "WARNING", "최소실시료 조항이 없습니다."))
        elif any(re.search(r"면제|감면|납부하지\s*(?:아니|않)|받지\s*(?:아니|않)", s) for s in hits):
            checklist.append(_item(name, "REVIEW", "최소실시료를 면제·감면하는 문구가 있습니다.", hits[0]))
        else:
            amounts = [a for s in hits for a in _amounts(s)]
            days = [int(d) for s in hits for d in _DAYS_RE.findall(s)]
            if amounts and max(amounts) < min_royalty:
                checklist.append(_item(name, "FAIL", f"기재 금액 {max(amounts):,}원이 기준 {min_royalty:,}원보다 적습니다.", hits[0]))
            elif days and min(days) > deadline:
                checklist.append(_item(name, "FAIL", f"납부 기한 {min(days)}일이 기준 {deadline}일보다 깁니다.", hits[0]))
            elif not amounts or not days:
                checklist.append(_item(name, "REVIEW", "금액 또는 납부 기한을 숫자로 찾지 못했습니다.", hits[0]))
            else:
                checklist.append(_item(name, "PASS", "금액·기한이 기준을 충족합니다.", hits[0]))

    name = f"불실시 해지특약 ({practice['due_diligence_years']}년 내 미착수 시 해지)"
    hits = _hits(sents, r"불실시|착수하지|실시하지\s*(?:아니|않)|사업화하지\s*(?:아니|않)")
    hits = [s for s in hits if "해지" in s]
    if not hits:
        checklist.append(_item(name, "WARNING", "불실시를 이유로 한 해지 조항이 없습니다."))
    elif any(re.search(r"해지할\s*수\s*없|해지하지\s*(?:아니|않|못)", s) for s in hits):
        checklist.append(_item(name, "REVIEW", "불실시해도 해지할 수 없다는 취지의 문구가 있습니다.", hits[0]))
    else:
        checklist.append(_item(name, "PASS", "불실시 해지 조항이 있습니다.", hits[0]))

    name = "매출 보고 및 장부 열람권"
    hits = _hits(sents, r"매출|장부|회계|실사|열람")
    if not hits:
        checklist.append(_item(name, "WARNING", "매출 보고·장부 열람 조항이 없습니다. 사후 감사 지적 대상이 될 수 있습니다."))
    elif any(re.search(r"의무(?:는|가)?\s*없|열람할\s*수\s*없|요구할\s*수\s*없|제출하지\s*(?:아니|않)|보고하지\s*(?:아니|않)", s) for s in hits):
        checklist.append(_item(name, "REVIEW", "보고·열람 의무를 배제하는 문구가 있습니다.", hits[0]))
    elif not _hits(hits, r"보고|제출|열람|실사"):
        checklist.append(_item(name, "REVIEW", "관련 단어는 있으나 보고·열람 의무 문장을 찾지 못했습니다.", hits[0]))
    else:
        checklist.append(_item(name, "PASS", "매출 보고 또는 장부 열람 조항이 있습니다.", hits[0]))

    name = "재실시권(Sub-license)·양도 제한"
    hits = _hits(sents, r"재실시|제3자에게\s*(?:실시|양도)|양도")
    if not hits:
        checklist.append(_item(name, "WARNING", "재실시권·양도 제한 조항이 없습니다."))
    elif any(re.search(r"자유롭게|승인\s*없이\s*(?:재실시|양도)(?:권을|를|할)?\s*(?:설정|허락)?\s*할\s*수\s*있", s) for s in hits):
        checklist.append(_item(name, "REVIEW", "승인 없이 재실시·양도를 허용하는 문구가 있습니다.", hits[0]))
    else:
        checklist.append(_item(name, "PASS", "재실시권·양도 관련 조항이 있습니다.", hits[0]))

    name = "계약 기간·실시 범위 명시"
    has_term = _hits(sents, r"(?:계약|실시|유효)\s*기간")
    has_scope = _hits(sents, r"실시\s*(?:지역|범위|분야)|지역|분야")
    if has_term and has_scope:
        checklist.append(_item(name, "PASS", "기간과 범위 조항이 있습니다.", has_term[0]))
    else:
        missing = [n for n, v in (("계약 기간", has_term), ("실시 범위(지역·분야)", has_scope)) if not v]
        checklist.append(_item(name, "WARNING", f"{', '.join(missing)} 조항을 찾지 못했습니다."))

    if is_exclusive:
        name = f"전용실시권 등록 ({art['exclusive_license_registration']})"
        hits = _hits(sents, r"등록")
        checklist.append(
            _item(name, "PASS", "등록 관련 조항이 있습니다.", hits[0])
            if hits
            else _item(name, "WARNING", "전용실시권 등록 및 비용 부담 조항이 없습니다 (등록해야 효력 발생).")
        )

    statuses = {c["status"] for c in checklist}
    if "FAIL" in statuses:
        summary = "수정 필요 (기준 위반 항목 있음)"
    elif "WARNING" in statuses:
        summary = "보완 권고 (누락 조항 있음)"
    elif "REVIEW" in statuses:
        summary = "확인 필요 (부정·면제·미기재 문구 있음)"
    else:
        summary = "자동 점검 항목 이상 없음 (최종 법무 검토 필요)"

    return {
        "license_type": license_type,
        "compliance_summary": summary,
        "checklist": checklist,
        "limitations": "문장 단위 키워드 점검입니다. 조항 간 관계·예외 조항·별지 내용은 판단하지 못합니다.",
        "legal_audit_basis": pm.audit_block(),
    }
