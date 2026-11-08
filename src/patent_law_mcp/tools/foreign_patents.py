"""해외 특허 조회 (Google Patents 공개 웹, 번호 검증)

지원: US(등록·공개), EP, WO(PCT 공개) — 종류 코드가 없으면 흔한 코드를 순서대로 시도합니다.
그 밖의 국가(JP·CN·DE 등)는 종류 코드까지 입력해야 합니다 (예: JP2020123456A, CN112345678A).
받은 문서의 국가·번호가 요청과 다르면 버립니다.
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from patent_law_mcp import net
from patent_law_mcp.config import settings

GOOGLE_URL = "https://patents.google.com/patent/{gid}/en"
_FOREIGN_RE = re.compile(r"^([A-Z]{2})\s*[-:]?\s*([0-9][0-9,.\s/\-]*[0-9])\s*([A-Z][0-9]?)?$")
_SUPPORTED = ("US", "EP", "WO", "JP", "CN", "DE", "GB", "FR", "CA", "AU", "TW")


@dataclass(frozen=True)
class ForeignNumber:
    country: str
    digits: str
    kinds: Tuple[str, ...]
    display: str


def is_foreign_identifier(identifier: str) -> bool:
    raw = identifier.strip().upper()
    return bool(re.match(r"^[A-Z]{2}", raw)) and not raw.startswith("KR") and not raw.startswith("PCT")


def parse_foreign_number(identifier: str) -> ForeignNumber:
    raw = identifier.strip().upper()
    if raw.startswith("PCT"):
        raise ValueError("PCT 출원번호(PCT/KR2020/...)로는 조회할 수 없습니다. 국제공개번호(WO2020123456 등)를 입력하십시오.")
    m = _FOREIGN_RE.match(raw)
    if not m or m.group(1) not in _SUPPORTED:
        raise ValueError(f"'{identifier}'은(는) 지원하지 않는 번호 형식입니다. 예: US10000000B2, US20200123456A1, EP1000000B1, WO2020123456A1")
    cc, digits, kind = m.group(1), re.sub(r"\D", "", m.group(2)), m.group(3)
    if kind:
        kinds: Tuple[str, ...] = (kind,)
    elif cc == "US":
        kinds = ("A1",) if len(digits) == 11 else ("B2", "B1")
    elif cc == "EP":
        kinds = ("B1", "A1", "A2")
    elif cc == "WO":
        kinds = ("A1", "A2", "A3")
    else:
        raise ValueError(f"{cc} 번호는 종류 코드까지 입력하십시오 (예: {cc}{digits}A).")
    if cc == "US" and len(digits) not in (7, 8, 11):
        raise ValueError("US 번호는 등록번호(7~8자리) 또는 공개번호(연도+7자리, 예: US 2020/0123456)여야 합니다.")
    if cc == "WO" and len(digits) != 10:
        raise ValueError("WO 번호는 연도 4자리 + 6자리 형식이어야 합니다 (예: WO 2020/123456).")
    return ForeignNumber(cc, digits, kinds, f"{cc} {digits}")


def _meta_numbers(data: Dict[str, Any]) -> List[Tuple[str, str]]:
    found = []
    for value in data.get("_meta_numbers", []):
        m = re.match(r"^([A-Z]{2}):?(\d+)", value)
        if m:
            found.append((m.group(1), m.group(2)))
    return found


def fetch_foreign_patent(identifier: str) -> Dict[str, Any]:
    from patent_law_mcp.tools.kipris_connector import RETRY_DELAY_SECONDS, parse_google_patents_html

    num = parse_foreign_number(identifier)
    attempts: List[Dict[str, str]] = []
    for kind in num.kinds:
        gid = f"{num.country}{num.digits}{kind}"
        resp = None
        for attempt in range(2):
            try:
                resp = net.http_get(GOOGLE_URL.format(gid=gid), headers={"Accept-Language": "en"},
                                    follow_redirects=True, timeout=settings.request_timeout_seconds)
            except httpx.HTTPError as e:
                attempts.append({"source": "Google Patents", "result": f"{gid}: 접속 실패 ({type(e).__name__})"})
                resp = None
                break
            if resp.status_code in (429, 503) and attempt == 0:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            break
        if resp is None:
            continue
        if resp.status_code == 404:
            attempts.append({"source": "Google Patents", "result": f"{gid}: 문서 없음 (404)"})
            continue
        if resp.status_code != 200:
            attempts.append({"source": "Google Patents", "result": f"{gid}: HTTP {resp.status_code} (429·503은 일시적 접속 제한)"})
            continue
        data = parse_google_patents_html(resp.text)
        if (num.country, num.digits) not in _meta_numbers(data):
            attempts.append({"source": "Google Patents", "result": f"{gid}: 문서 번호가 요청과 달라 버림"})
            continue
        attempts.append({"source": "Google Patents", "result": f"{gid}: 국가·번호 일치 확인"})
        data.pop("_check", None)
        data.pop("_meta_numbers", None)
        applicants = data.get("applicants") or []
        warnings = [] if data.get("claims") else ["이 문서 페이지에서 청구항을 읽지 못했습니다 (원문 언어 청구항만 있거나 미제공)."]
        return {
            "found": True,
            "requested": {"identifier": identifier, "interpreted_as": f"{num.country} 특허 문서", "number": f"{num.display} {kind}"},
            "country": num.country,
            **data,
            "register_number": f"{num.country}{num.digits}{kind}" if kind.startswith("B") or num.country == "US" and len(num.digits) <= 8 else "",
            "publication_number": f"{num.country}{num.digits}{kind}",
            "source": "Google Patents 공개 웹",
            "applicant": ", ".join(applicants) if applicants else "미확인",
            "ipc_code": "",
            "warnings": warnings,
            "attempts": attempts,
            "note": "해외 특허의 법적 상태·존속기간은 각국 규정이 달라 이 도구의 한국 기준 계산기를 쓰지 마십시오.",
        }
    return {
        "found": False,
        "requested": {"identifier": identifier, "interpreted_as": f"{num.country} 특허 문서", "number": num.display},
        "error": f"{num.display}의 특허 정보를 확인하지 못했습니다.",
        "attempts": attempts,
        "next_steps": ["종류 코드(B1·B2·A1 등)를 붙여 다시 조회하거나, 잠시 후 재시도하십시오."],
    }
