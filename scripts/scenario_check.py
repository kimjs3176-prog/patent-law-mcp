#!/usr/bin/env python3
"""MCP 실사용 시나리오 점검 (서버를 별도 프로세스로 띄워 MCP 프로토콜로 호출)

  uv run python scripts/scenario_check.py            # stdio + HTTP 시나리오 전체
  uv run python scripts/scenario_check.py --offline  # 네트워크가 필요한 시나리오 제외

네트워크 시나리오는 Google Patents(공개 웹)를 실제로 조회합니다. 일시적 접속 제한(503)이면 SKIP으로 표시합니다.
"""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

GAZETTE = """(12) 등록특허공보(B1)
(51) 국제특허분류(Int. Cl.)
     A23L 7/10 (2006.01)
(21) 출원번호 10-2010-0062402
(11) 등록번호 10-1070281
(73) 특허권자
     대한민국(농촌진흥청장)
     전라북도 전주시 덕진구 농생명로 300
(54) 발명의 명칭 굳지 않는 떡의 제조방법
(57) 요 약
본 발명은 전분의 노화를 방지하여 굳지 않는 떡을 제조하는 방법에 관한 것이다.
특허청구의 범위
청구항 1
쌀가루를 증자하는 단계; 및 증자된 반죽을 펀칭하는 단계;를 포함하는 굳지 않는 떡의 제조방법.
청구항 2
제1항에 있어서, 상기 펀칭 단계는 50~80℃에서 수행되는 제조방법.
명 세 서
"""

CONTRACT = """제2조(계약기간) 계약기간은 3년으로 한다. 실시지역은 대한민국, 실시분야는 식품 제조로 한다.
제3조(최소실시료) 을은 최소실시료로 금 3,000,000원을 계약체결일로부터 60일 이내에 납부한다.
제4조(해지) 을이 계약일부터 2년 이내에 정당한 사유 없이 사업화에 착수하지 아니한 경우 갑은 해지할 수 있다.
제5조(보고) 을은 매 사업연도 종료 후 60일 이내에 매출 보고서를 제출하며, 갑은 장부 열람을 요구할 수 있다.
제6조(재실시) 을은 갑의 사전 서면 승인 없이 재실시권을 설정할 수 없다.
제7조(등록) 전용실시권 등록 비용은 을이 부담한다."""


class Skip(Exception):
    pass


Result = Tuple[str, str, str, str]  # (시나리오, 단계, 결과, 비고)


async def call(session: ClientSession, tool: str, args: Dict[str, Any]) -> Tuple[bool, Any]:
    res = await session.call_tool(tool, args)
    text = res.content[0].text if res.content else ""
    try:
        data = json.loads(text)
    except ValueError:
        data = text
    return bool(res.isError), data


def network_guard(data: Dict[str, Any]) -> None:
    attempts = " ".join(a.get("result", "") for a in data.get("attempts", [])) if isinstance(data, dict) else ""
    if not data.get("found") and ("503" in attempts or "429" in attempts or "접속 실패" in attempts):
        raise Skip(f"일시적 접속 제한/네트워크: {attempts[:80]}")


async def run_steps(session: ClientSession, offline: bool) -> List[Result]:
    results: List[Result] = []

    async def step(scenario: str, name: str, tool: str, args: Dict[str, Any],
                   check: Callable[[bool, Any], Optional[str]], network: bool = False) -> Any:
        if network and offline:
            results.append((scenario, name, "SKIP", "--offline"))
            return None
        try:
            is_error, data = await call(session, tool, args)
            if network and isinstance(data, dict):
                network_guard(data)
            problem = check(is_error, data)
            results.append((scenario, name, "PASS" if problem is None else "FAIL", problem or ""))
            return data
        except Skip as e:
            results.append((scenario, name, "SKIP", str(e)))
        except Exception as e:  # noqa: BLE001
            results.append((scenario, name, "FAIL", f"{type(e).__name__}: {e}"[:160]))
        return None

    def ok(cond: bool, why: str) -> Optional[str]:
        return None if cond else why

    # 0. 서버 기본
    tools = await session.list_tools()
    names = {t.name for t in tools.tools}
    results.append(("0. 서버", "도구 목록", "PASS" if len(names) == 25 else "FAIL", f"{len(names)}개"))

    # 1. 기술이전 상담 (국유특허·실데이터)
    s = "1. 기술이전 상담"
    patent = await step(s, "등록번호 조회·검증", "fetch_patent_smart", {"patent_identifier": "10-1070281"},
                        lambda e, d: ok(not e and d.get("found") and d["register_number"] == "10-1070281"
                                        and d["application_number"] == "10-2008-0119257", str(d)[:120]), network=True)
    if patent and patent.get("claims"):
        await step(s, "권리범위 1차 대조", "verify_tech_transfer_scope_match",
                   {"claim_text": patent["claims"][0], "target_product_spec": "슬러지를 투입구로 넣어 열풍주입부의 열풍으로 건조하고 배출구로 내보내는 건조부를 갖춘 설비"},
                   lambda e, d: ok(not e and "/" in d["matched_elements"], str(d)[:120]))
    else:
        results.append((s, "권리범위 1차 대조", "SKIP", "선행 조회에서 청구항을 확보하지 못함"))
    await step(s, "전용실시 계약조건", "design_licensing_terms",
               {"patent_id": "10-1070281", "license_type": "exclusive", "company_scale": "sme", "expected_sales_annual": 500_000_000, "share_rate": 0.3},
               lambda e, d: ok(not e and d["financial_terms"]["lump_sum_fee_krw"] >= 3_000_000
                               and len(d["financial_terms"]["private_contract_exceptions"]) == 7
                               and d["financial_terms"]["estimated_annual_running_royalty_krw"] > 0, str(d)[:120]))
    await step(s, "계약서 검토 (정상)", "review_licensing_contract", {"contract_text": CONTRACT},
               lambda e, d: ok(not e and d["compliance_summary"].startswith("자동 점검 항목 이상 없음"), d.get("compliance_summary", "")))
    await step(s, "계약서 검토 (면제 문구)", "review_licensing_contract",
               {"contract_text": "갑은 최소실시료를 면제한다. 을이 불실시하더라도 갑은 해지할 수 없다."},
               lambda e, d: ok(not e and not d["compliance_summary"].startswith("자동 점검 항목 이상 없음"), d.get("compliance_summary", "")))

    # 2. 공보 붙여넣기
    s = "2. 공보 붙여넣기"
    await step(s, "공보 분해", "parse_raw_patent_text", {"raw_text": GAZETTE},
               lambda e, d: ok(not e and d["applicant"] == "대한민국(농촌진흥청장)"
                               and d["ipc_code"] == "A23L 7/10" and d["claims_count"] == 2
                               and d["independent_claim_numbers"] == [1], str(d)[:160]))

    # 3. 직무발명·보상 (국유특허)
    s = "3. 직무발명·보상"
    await step(s, "직무발명 신고", "process_invention_disclosure",
               {"title": "굳지 않는 떡", "inventor_names": ["홍길동", "김연구"], "has_prior_publication": True},
               lambda e, d: ok(not e and "500,000원" in " ".join(d["administrative_steps"]) and "12개월" in d["novelty_risk"], str(d)[:120]))
    await step(s, "처분보상금 (재직·퇴직)", "calculate_disposal_compensation",
               {"contract_income_krw": 50_000_000, "direct_expenses_krw": 6_000_000,
                "inventor_shares": [{"name": "홍길동", "share_rate": 0.7},
                                    {"name": "김연구", "share_rate": 0.3, "employment_status": "retired"}]},
               lambda e, d: ok(not e and d["total_compensation_krw"] == 22_000_000
                               and d["payment_table"][1]["income_type"].startswith("기타소득"), str(d)[:120]))
    await step(s, "지분 합계 오류 차단", "calculate_disposal_compensation",
               {"contract_income_krw": 1000, "inventor_shares": [{"name": "A", "share_rate": 0.7}, {"name": "B", "share_rate": 0.2}]},
               lambda e, d: ok(e and "지분 합계" in str(d), str(d)[:120]))

    # 4. 국유특허 처분
    s = "4. 국유특허 처분"
    await step(s, "미활용 특허 무상실시", "evaluate_unutilized_free_license", {"registration_years_elapsed": 4, "applicant_scale": "sme"},
               lambda e, d: ok(not e and d["eligible_for_free_license"] and "2%로" in d["subsequent_terms"]["sme_preferential_rate"], str(d)[:120]))
    await step(s, "전용실시 갱신 (제5호 사유)", "evaluate_exclusive_renewal",
               {"cumulative_commercial_revenue_krw": 10, "cumulative_investment_krw": 5, "expiry_days_remaining": 40, "inventor_info_unavailable": True},
               lambda e, d: ok(not e and d["assessment"].startswith("갱신 사유 충족"), d.get("assessment", "")))
    await step(s, "정책 기준값 조회", "get_policy_table", {},
               lambda e, d: ok(not e and d["metadata"]["notice_id"] == "지식재산처고시 제2025-4호", str(d)[:80]))

    # 5. 기한·권리 관리
    s = "5. 기한·권리 관리"
    await step(s, "우선권 기한 (연휴)", "calculate_patent_deadline", {"base_date": "2024-10-03", "preset": "convention_priority"},
               lambda e, d: ok(not e and d["deadline"] == "2025-10-10", str(d)[:120]))
    await step(s, "PCT 31개월", "calculate_patent_deadline", {"base_date": "2023-01-16", "preset": "pct_national_phase"},
               lambda e, d: ok(not e and d["nominal_end"] == "2025-08-16" and d["deadline"] == "2025-08-18", str(d)[:120]))
    await step(s, "존속기간", "calculate_patent_term", {"application_date": "2010-06-30", "as_of": "2026-11-08"},
               lambda e, d: ok(not e and d["expiry_date"] == "2030-06-30", str(d)[:120]))
    await step(s, "연차료 상태 (추가납부기간)", "calculate_annuity_schedule",
               {"registration_date": "2011-09-28", "application_date": "2010-06-30", "paid_through_year": 3, "as_of": "2014-12-01"},
               lambda e, d: ok(not e and d["status"].startswith("추가납부기간"), d.get("status", "")))
    await step(s, "권리 상태 종합 (실데이터)", "check_patent_rights_status",
               {"patent_identifier": "10-1070281", "registration_date": "2011-10-06", "paid_through_year": 15, "as_of": "2026-11-08"},
               lambda e, d: ok(not e and d["term"]["expiry_date"] == "2028-11-28" and d["annuity"]["schedule"][0]["year"] == 16, str(d)[:160]),
               network=True)

    # 6. 해외 특허
    s = "6. 해외 특허"
    await step(s, "US 등록번호 (종류 코드 없이)", "fetch_patent_smart", {"patent_identifier": "US 10,000,000"},
               lambda e, d: ok(not e and d.get("found") and d["publication_number"] == "US10000000B2" and len(d["claims"]) == 20, str(d)[:160]),
               network=True)

    # 7. 요약 근거 확인 (업스트림 규칙)
    s = "7. 요약 근거 확인"
    await step(s, "효과 수치 근거", "ground_summary_figures",
               {"summary_text": "에너지를 30% 절감한다. 수율이 2배 향상된다.", "source_text": "본 발명은 수율을 2배 향상시킨다."},
               lambda e, d: ok(not e and d["removed_figures"] == ["30%"] and "2배" in d["sanitized_text"], str(d)[:160]))

    # 8. 인증키가 없을 때
    s = "8. 인증키 없음"
    # 키가 없으면 Google Patents로 대신 검색한다. Google이 일시 제한하면 결과를 지어내지 않고 이유와 대안을 돌려줘야 한다
    await step(s, "특허 검색 (키 없음 → Google)", "search_patents", {"query": "떡"},
               lambda e, d: ok(not e and ((d["found"] and d["source"].startswith("Google Patents") and d["results"][0]["publication_number"].startswith("KR"))
                                          or (not d["found"] and "x-api-key" in d.get("how_to", ""))), str(d)[:160]), network=True)
    await step(s, "법령 조문", "get_law_article", {"law_name": "특허법", "article": "제100조"},
               lambda e, d: ok(not e and d["found"] is False and "LAW_OC" in d["error"], str(d)[:120]))
    await step(s, "출원번호 조회 (키 없음)", "fetch_patent_smart", {"patent_identifier": "10-2010-0062402"},
               lambda e, d: ok(not e and d["found"] is False and any("publication" in n for n in d["next_steps"]), str(d)[:120]))

    # 9. 잘못된 입력·없는 특허
    s = "9. 오류 처리"
    await step(s, "열거형 오류", "design_licensing_terms", {"patent_id": "x", "license_type": "전용실시"},
               lambda e, d: ok(e and "license_type" in str(d), str(d)[:120]))
    await step(s, "번호 형식 오류", "fetch_patent_smart", {"patent_identifier": "12345"},
               lambda e, d: ok(e and "번호 형식" in str(d), str(d)[:120]))
    await step(s, "없는 특허", "fetch_patent_smart", {"patent_identifier": "10-9999999"},
               lambda e, d: ok(not e and d["found"] is False and "title" not in d, str(d)[:120]), network=True)

    # 10. 기관 유형별 프로파일
    s = "10. 프로파일"
    await step(s, "대학·출연연 보상 (비율 미입력)", "calculate_disposal_compensation",
               {"contract_income_krw": 10_000_000, "inventor_shares": [{"name": "A", "share_rate": 1.0}], "profile": "public_research"},
               lambda e, d: ok(e and "payout_ratio" in str(d), str(d)[:120]))
    await step(s, "대학·출연연 보상 (비율 입력)", "calculate_disposal_compensation",
               {"contract_income_krw": 10_000_000, "inventor_shares": [{"name": "A", "share_rate": 1.0}], "profile": "public_research", "payout_ratio": 0.6},
               lambda e, d: ok(not e and d["total_compensation_krw"] == 6_000_000, str(d)[:120]))
    await step(s, "민간 기업 신고 (예약승계)", "process_invention_disclosure",
               {"title": "센서", "inventor_names": ["A"], "profile": "private_company"},
               lambda e, d: ok(not e and "발명 완성 때부터 사용자에게 승계됩니다" in d["succession_rule"], str(d)[:120]))
    # 11. 국가직무발명특허권 업무 흐름 (신고 → 등록보상 → 처분 방식 → 실시료 → 수탁기관 → 분쟁)
    s = "11. 국가직무발명 업무"
    await step(s, "신고 서류·부기 명칭", "process_invention_disclosure",
               {"title": "굳지 않는 떡", "inventor_names": ["홍길동"], "profile": "national"},
               lambda e, d: ok(not e and d["required_documents"][0].startswith("직무발명신고서") and "1차 소속기관" in d["applicant_name_rule"], str(d)[:160]))
    await step(s, "등록보상금 배분", "calculate_registration_compensation",
               {"right_type": "patent", "inventor_shares": [{"name": "홍길동", "share_rate": 0.6}, {"name": "김연구", "share_rate": 0.4}]},
               lambda e, d: ok(not e and d["total_compensation_krw"] == 500_000 and d["payment_table"][1]["compensation_krw"] == 200_000, str(d)[:160]))
    await step(s, "처분 방식 (전용·입찰)", "plan_national_disposal",
               {"disposal_type": "exclusive", "bid_date": "2026-12-31", "contract_start_date": "2027-01-15", "patent_expiry_date": "2030-06-30"},
               lambda e, d: ok(not e and d["method"].startswith("경쟁입찰") and d["bid_notice"]["notice_deadline"] == "2026-12-01"
                               and d["contract_term"]["latest_end_date"] == "2030-06-30", str(d)[:160]))
    await step(s, "실시료 예정가격", "calculate_royalty_estimate",
               {"annual_factory_prices_krw": [10_000, 12_000, 14_000], "share_rate": 0.5, "annual_sales_quantities": [1_000, 2_000, 3_000]},
               lambda e, d: ok(not e and d["estimated_price_krw"] == 1_080_000, str(d)[:160]))
    await step(s, "기본율 범위 밖 차단", "calculate_royalty_estimate",
               {"annual_factory_prices_krw": [10_000], "share_rate": 0.5, "base_rate": 0.05},
               lambda e, d: ok(e and "4% 이하" in str(d), str(d)[:160]))
    await step(s, "수탁기관 분기 보고", "get_trustee_obligations", {"as_of": "2026-11-22", "disposal_income_krw": 10_000_000},
               lambda e, d: ok(not e and d["quarterly_reports"][0]["report_due"] == "2027-01-15"
                               and d["contribution_compensation"]["upper_bound_krw"] == 1_500_000, str(d)[:160]))
    await step(s, "심결 패소 대응", "guide_national_dispute", {"case_type": "trial", "trial_lost": True},
               lambda e, d: ok(not e and any("30일 이내" in x for x in d["steps"]), str(d)[:160]))
    await step(s, "보유 특허 연차료 일괄", "check_portfolio_annuities",
               {"as_of": "2026-11-22", "patents": [
                   {"patent_id": "A", "registration_date": "2023-08-01", "application_date": "2021-01-01"},
                   {"patent_id": "B", "registration_date": "2024-06-01", "application_date": "2022-01-01"}]},
               lambda e, d: ok(not e and d["patents"][0]["patent_id"] == "A" and d["patents"][0]["category"] == "추가납부기간", str(d)[:160]))

    await step(s, "근거 법령 개정 여부 (실데이터)", "check_legal_source_updates", {"refresh": True},
               lambda e, d: ok(not e and not d["errors"] and d["baseline_verified_on"] and d["summary"] in ("변경 없음", "변경 있음 — 원문 검토 필요"),
                               str(d)[:200]), network=True)

    # 12. 근거 부족·불완전 입력에서 답변이 과도하게 단정되지 않는지 확인
    s = "12. 답변 품질"
    await step(s, "구성요소 명시적 부정", "verify_tech_transfer_scope_match",
               {"claim_text": "센서와 모터를 포함하는 장치.", "target_product_spec": "센서는 있음. 모터는 없음."},
               lambda e, d: ok(not e and d["matched_elements"] == "0/1", str(d)[:180]))
    return results


async def stdio_session(offline: bool) -> List[Result]:
    env = {**os.environ, "PATENT_LAW_MCP_CACHE": "off"}
    for k in ("KIPRIS_API_KEY", "LAW_OC", "PATENT_LAW_MCP_PROFILE", "PATENT_LAW_MCP_POLICY_FILE"):
        env.pop(k, None)
    params = StdioServerParameters(command=sys.executable, args=["-m", "patent_law_mcp.server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await run_steps(session, offline)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def http_session() -> List[Result]:
    port, token = free_port(), "scenario-token"
    env = {**os.environ, "PATENT_LAW_MCP_TOKEN": token, "PATENT_LAW_MCP_CACHE": "off"}
    proc = subprocess.Popen([sys.executable, "-m", "patent_law_mcp.server", "--transport", "streamable-http", "--port", str(port)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results: List[Result] = []
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.2)
        url = f"http://127.0.0.1:{port}/mcp"
        # 로컬 테스트 서버에는 시스템 프록시를 적용하지 않는다.
        def local_client(**kwargs):
            return httpx.AsyncClient(trust_env=False, **kwargs)

        async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"},
                                        httpx_client_factory=local_client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                n = len((await session.list_tools()).tools)
                _, data = await call(session, "calculate_patent_term", {"application_date": "2010-06-30"})
                results.append(("13. HTTP 배포", "토큰 인증 후 호출", "PASS" if n == 25 and data["expiry_date"] == "2030-06-30" else "FAIL", f"도구 {n}개"))
        r = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                       headers={"accept": "application/json, text/event-stream"}, trust_env=False)
        results.append(("13. HTTP 배포", "토큰 없이 거부", "PASS" if r.status_code == 401 else "FAIL", f"HTTP {r.status_code}"))
        bad = subprocess.run([sys.executable, "-m", "patent_law_mcp.server", "--transport", "streamable-http", "--host", "0.0.0.0"],
                             env={k: v for k, v in env.items() if k != "PATENT_LAW_MCP_TOKEN"}, capture_output=True, text=True, timeout=20)
        results.append(("13. HTTP 배포", "토큰 없는 외부 바인딩 거부", "PASS" if bad.returncode != 0 and "PATENT_LAW_MCP_TOKEN" in bad.stderr else "FAIL", ""))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    results = asyncio.run(stdio_session(args.offline))
    try:
        results += asyncio.run(http_session())
    except Exception as e:
        results.append(("13. HTTP 배포", "HTTP 시나리오 실행", "FAIL", type(e).__name__))
    width = max(len(r[1]) for r in results)
    for scenario, name, status, note in results:
        print(f"{status:4}  {scenario:<14} {name:<{width}}  {note}")
    counts = {k: sum(1 for r in results if r[2] == k) for k in ("PASS", "FAIL", "SKIP")}
    print(f"\n합계: PASS {counts['PASS']} · FAIL {counts['FAIL']} · SKIP {counts['SKIP']}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())

