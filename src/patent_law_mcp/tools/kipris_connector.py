"""특허 원문 수집기 (KIPRIS Plus 공식 API + Google Patents 공개 웹)

- 출원번호: KIPRIS Plus API로만 조회합니다 (환경변수 KIPRIS_API_KEY 필요).
  Google Patents는 출원번호로 직접 조회할 수 없고, 같은 숫자의 공개번호는 전혀 다른 특허이기 때문입니다.
- 등록번호·공개번호: Google Patents에서 조회한 뒤, 받은 문서의 번호가 요청 번호와 같은지 검증합니다.
  KIPRIS 키가 있으면 확인된 출원번호로 KIPRIS 공식 서지를 이어서 조회합니다.
- 어느 경로로도 확인하지 못하면 다른 특허나 가상 데이터를 대신 돌려주지 않고 found=False와 사유를 반환합니다.

KIPRIS 응답 구조는 patent-video-skill/scripts/kipris.py의 parse()와 같은 경로를 사용합니다.
"""

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from pydantic import Field

from patent_law_mcp import net
from patent_law_mcp.config import settings
from patent_law_mcp.tools.analysis import evaluate_commercialization, summarize_patent
from patent_law_mcp.tools.claim_utils import normalize_ws

KIPRIS_API_BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch"
GOOGLE_PATENTS_URL = "https://patents.google.com/patent/{gid}/ko"
RETRY_DELAY_SECONDS = 2.0

NumberType = Literal["auto", "application", "registration", "publication"]
_KIND_LABELS = {"application": "출원번호", "registration": "등록번호", "publication": "공개번호"}


@dataclass(frozen=True)
class KrPatentNumber:
    kind: str     # application | registration | publication
    digits: str   # 출원·공개: 13자리(10YYYYNNNNNNN), 등록: 9자리(10NNNNNNN)
    display: str
    google_id: Optional[str]

    @property
    def label(self) -> str:
        return _KIND_LABELS[self.kind]


def parse_kr_patent_number(identifier: str, number_type: NumberType = "auto") -> KrPatentNumber:
    """한국 특허 출원·등록·공개번호를 해석합니다. 형식이 맞지 않으면 ValueError를 냅니다.

    auto 판정: 7·9자리 → 등록번호, 13자리 → 출원번호.
    13자리 공개번호(10-YYYY-NNNNNNN)는 출원번호와 형식이 같으므로 number_type="publication"으로 지정해야 합니다.
    """
    raw = re.sub(r"[\s\-제호]", "", identifier.strip().upper())
    m = re.fullmatch(r"KR(\d+)([AB]\d?)", raw)
    if m:
        digits, kind_code = m.groups()
        if kind_code.startswith("B"):
            inferred = "registration"
        elif len(digits) == 13:
            inferred = "application"
        else:
            inferred = "publication"
            if len(digits) == 11:
                digits = "10" + digits
        if number_type == "auto":
            number_type = inferred
    else:
        digits = re.sub(r"\D", "", raw)

    if number_type == "auto":
        if len(digits) in (7, 9):
            number_type = "registration"
        elif len(digits) == 13:
            number_type = "application"
        else:
            raise ValueError(f"'{identifier}'은(는) 인식할 수 없는 번호 형식입니다. 예: 10-2010-0062402(출원), 10-1070281(등록)")

    if len(digits) in (9, 13) and digits.startswith("20"):
        raise ValueError("실용신안(20-)은 지원하지 않습니다. 특허(10-) 번호를 입력하십시오.")

    if number_type == "registration":
        if len(digits) == 7:
            digits = "10" + digits
        elif len(digits) == 13 and digits.startswith("10") and digits.endswith("0000"):
            digits = digits[:9]  # KIPRIS 등록번호 표기(10NNNNNNN0000)
        if not (len(digits) == 9 and digits.startswith("10")):
            raise ValueError(f"등록번호 형식이 아닙니다: '{identifier}' (예: 10-1070281)")
        return KrPatentNumber("registration", digits, f"10-{digits[2:]}", f"KR{digits}B1")

    if not (len(digits) == 13 and digits.startswith("10")):
        raise ValueError(f"{_KIND_LABELS[number_type]} 형식이 아닙니다: '{identifier}' (예: 10-2010-0062402)")
    year = int(digits[2:6])
    if not 1948 <= year <= date.today().year + 1:
        raise ValueError(f"번호의 연도({year})가 올바르지 않습니다: '{identifier}'")
    display = f"10-{digits[2:6]}-{digits[6:]}"
    google_id = f"KR{digits[2:]}A" if number_type == "publication" else None
    return KrPatentNumber(number_type, digits, display, google_id)


def _http_get(url: str, **kwargs: Any) -> httpx.Response:
    return net.http_get(url, **kwargs)


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def _format_app(d: str) -> str:
    return f"{d[:2]}-{d[2:6]}-{d[6:13]}" if len(d) >= 13 else d


def _format_reg(d: str) -> str:
    return f"{d[:2]}-{d[2:9]}" if len(d) >= 9 else d


# ---------------------------------------------------------------- Google Patents
def parse_google_patents_html(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    def meta(name: str, scheme: Optional[str] = None) -> List[str]:
        attrs = {"name": name, **({"scheme": scheme} if scheme else {})}
        return [normalize_ws(m.get("content", "")) for m in soup.find_all("meta", attrs) if m.get("content")]

    def first_meta(name: str) -> str:
        values = meta(name)
        return values[0] if values else ""

    claims: List[str] = []
    section = soup.find("section", {"itemprop": "claims"})
    if section:
        for div in section.find_all("div", class_="claim", attrs={"num": True}):
            if div.find_parent("div", class_="claim"):
                continue
            text = re.sub(r"^\d+\s*[.)]\s*", "", normalize_ws(div.get_text(" ", strip=True)))
            if text:
                claims.append(text)

    abstract_div = soup.find("div", class_="abstract") or soup.find("section", {"itemprop": "abstract"})
    filing = soup.find(itemprop="filingDate")
    status = soup.find(itemprop="legalStatusIfi")
    cpc = []
    for li in soup.find_all("li", itemprop="classifications"):
        code = li.find(itemprop="Code")
        if li.find(itemprop="Leaf") and code and code.text.strip() not in cpc:
            cpc.append(code.text.strip())

    def number_part(value: str) -> str:
        # "KR:1020080119257A" / "KR:101070281:B1" / "KR:20100062402:A" -> 국가코드·종류코드를 뺀 번호
        m = re.search(r"KR:?(\d+)", value)
        return m.group(1) if m else ""

    events = []
    for ev in soup.find_all(attrs={"itemprop": "events"}):
        fields = {c.get("itemprop"): normalize_ws(c.get_text(" ", strip=True)) for c in ev.find_all(attrs={"itemprop": True})}
        if fields.get("title"):
            events.append({"date": fields.get("date", ""), "title": fields["title"], "type": fields.get("type", "")})

    app_d = number_part(first_meta("citation_patent_application_number"))
    reg_d = number_part(first_meta("citation_patent_number"))
    pub_d = number_part(first_meta("citation_patent_publication_number"))

    return {
        "title": first_meta("DC.title"),
        "application_number": _format_app(app_d) if app_d else "",
        "application_date": filing.text.strip() if filing else "",
        "register_number": _format_reg(reg_d) if reg_d else "",
        "publication_number": _format_app("10" + pub_d) if len(pub_d) == 11 else "",
        "applicants": meta("DC.contributor", "assignee"),
        "inventors": meta("DC.contributor", "inventor"),
        "register_status": f"{status.text.strip()} (Google 추정 상태, 공식 법적 상태 아님)" if status else "",
        "ipc_codes": [],
        "cpc_codes": cpc,
        "abstract": normalize_ws(abstract_div.get_text(" ", strip=True)) if abstract_div else "",
        "claims": claims,
        "events": events,
        "_check": {"application": app_d, "registration": reg_d, "publication": ("10" + pub_d) if len(pub_d) == 11 else ""},
    }


def fetch_from_google_patents(num: KrPatentNumber) -> Tuple[Optional[Dict[str, Any]], str]:
    if not num.google_id:
        return None, "Google Patents는 출원번호로 조회할 수 없습니다 (같은 숫자의 공개번호는 다른 특허입니다)."

    url = GOOGLE_PATENTS_URL.format(gid=num.google_id)
    headers = {"Accept-Language": "ko-KR,ko;q=0.9"}
    resp = None
    for attempt in range(2):
        try:
            resp = _http_get(url, headers=headers, follow_redirects=True, timeout=settings.request_timeout_seconds)
        except httpx.HTTPError as e:
            return None, f"Google Patents 접속 실패 ({type(e).__name__})"
        if resp.status_code in (429, 503) and attempt == 0:
            time.sleep(RETRY_DELAY_SECONDS)
            continue
        break

    if resp.status_code == 404:
        return None, f"Google Patents에 {num.google_id} 문서가 없습니다 (404)."
    if resp.status_code != 200:
        return None, f"Google Patents 응답 오류 (HTTP {resp.status_code}; 429·503은 일시적 접속 제한이므로 잠시 후 재시도)"

    data = parse_google_patents_html(resp.text)
    found = data["_check"].get(num.kind, "")
    if found != num.digits:
        return None, (
            f"받은 문서의 {num.label}({found or '없음'})가 요청 번호({num.digits})와 달라 결과를 버렸습니다."
        )
    if not data["claims"]:
        return None, "문서는 찾았지만 청구항을 읽지 못했습니다 (페이지 구조 변경 가능성)."
    data["source"] = "Google Patents 공개 웹"
    return data, f"Google Patents에서 {num.label} 일치 확인"


# ---------------------------------------------------------------- KIPRIS Plus
def _text(el: Optional[ET.Element], path: str) -> str:
    if el is None:
        return ""
    n = el.find(path)
    return (n.text or "").strip() if n is not None and n.text else ""


def parse_kipris_xml(raw: bytes) -> Dict[str, Any]:
    """KIPRIS getBibliographyDetailInfoSearch 응답 XML을 해석합니다 (patent-video-skill kipris.parse와 동일 경로)."""
    root = ET.fromstring(raw)
    item = root.find(".//item")
    if item is None:
        msg = _text(root, ".//resultMsg") or _text(root, ".//errMsg") or "응답에 특허 정보(item)가 없습니다."
        raise LookupError(msg)

    b = item.find("biblioSummaryInfoArray/biblioSummaryInfo")
    ipc = [t for t in (_text(i, "ipcNumber") for i in item.findall("ipcInfoArray/ipcInfo")) if t]
    reg_d = _digits(_text(b, "registerNumber"))
    open_d = _digits(_text(b, "openNumber"))
    return {
        "title": _text(b, "inventionTitle"),
        "application_number": _format_app(_digits(_text(b, "applicationNumber"))),
        "application_date": _text(b, "applicationDate"),
        "register_number": _format_reg(reg_d) if reg_d else "",
        "register_date": _text(b, "registerDate"),
        "publication_number": _format_app(open_d) if len(open_d) >= 13 else "",
        "register_status": _text(b, "registerStatus"),
        "ipc_codes": ipc,
        "cpc_codes": [],
        "applicants": [t for t in (_text(a, "name") for a in item.findall("applicantInfoArray/applicantInfo")) if t],
        "inventors": [t for t in (_text(a, "name") for a in item.findall("inventorInfoArray/inventorInfo")) if t],
        "abstract": _text(item, "abstractInfoArray/abstractInfo/astrtCont"),
        "claims": [t for t in (_text(c, "claim") for c in item.findall("claimInfoArray/claimInfo")) if t],
        "_check": {"application": _digits(_text(b, "applicationNumber"))},
    }


def fetch_from_kipris_api(application_digits: str, service_key: str) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        resp = _http_get(
            KIPRIS_API_BASE,
            params={"applicationNumber": application_digits, "ServiceKey": service_key},
            timeout=settings.request_timeout_seconds,
        )
    except httpx.HTTPError as e:
        return None, f"KIPRIS 접속 실패 ({type(e).__name__})"
    if resp.status_code != 200:
        return None, f"KIPRIS 응답 오류 (HTTP {resp.status_code})"
    try:
        data = parse_kipris_xml(resp.content)
    except ET.ParseError:
        return None, "KIPRIS 응답을 XML로 해석하지 못했습니다."
    except LookupError as e:
        return None, f"KIPRIS: {e} (인증키·출원번호를 확인하십시오)"

    if data["_check"]["application"] != application_digits:
        return None, f"KIPRIS가 다른 출원번호({data['_check']['application'] or '없음'})를 반환해 결과를 버렸습니다."
    data["source"] = "KIPRIS Plus 공식 Open API"
    return data, "KIPRIS에서 출원번호 일치 확인"


# ---------------------------------------------------------------- 통합 조회
def fetch_patent_smart(
    patent_identifier: Annotated[str, Field(min_length=5, max_length=40)],
    number_type: NumberType = "auto",
) -> Dict[str, Any]:
    """출원·등록·공개번호로 특허 서지·초록·청구항을 조회하고, 받은 문서가 요청한 번호와 일치하는지 검증합니다.

    Args:
        patent_identifier: 특허번호 (예: "10-1070281", "10-2010-0062402", "KR101070281B1")
        number_type: 번호 종류 ("auto", "application"(출원), "registration"(등록), "publication"(공개)).
            auto는 7·9자리를 등록번호, 13자리를 출원번호로 봅니다. 13자리 공개번호는 "publication"으로 지정하십시오.

    출원번호 조회에는 KIPRIS Plus 인증키(환경변수 KIPRIS_API_KEY)가 필요합니다.
    확인하지 못하면 found=False와 시도 내역을 반환하며, 다른 특허를 대신 돌려주지 않습니다.
    """
    num = parse_kr_patent_number(patent_identifier, number_type)
    key = settings.kipris_api_key
    attempts: List[Dict[str, str]] = []
    data: Optional[Dict[str, Any]] = None

    if num.kind == "application":
        if key:
            data, msg = fetch_from_kipris_api(num.digits, key)
            attempts.append({"source": "KIPRIS Plus", "result": msg})
        else:
            attempts.append({"source": "KIPRIS Plus", "result": "인증키(KIPRIS_API_KEY)가 설정되지 않아 조회하지 않음"})
            attempts.append({"source": "Google Patents", "result": "출원번호로는 조회할 수 없음"})
    else:
        data, msg = fetch_from_google_patents(num)
        attempts.append({"source": "Google Patents", "result": msg})
        app_digits = data["_check"]["application"] if data else ""
        if data and key and app_digits:
            official, kmsg = fetch_from_kipris_api(app_digits, key)
            attempts.append({"source": "KIPRIS Plus", "result": kmsg})
            if official:
                official["source"] = "KIPRIS Plus 공식 Open API (출원번호는 Google Patents에서 확인)"
                data = official

    requested = {"identifier": patent_identifier, "interpreted_as": num.label, "number": num.display}
    if not data:
        next_steps = []
        if num.kind == "application":
            next_steps.append("등록번호(10-XXXXXXX)나 공개번호로 다시 조회하거나, KIPRIS_API_KEY를 설정하십시오.")
            next_steps.append("입력한 13자리 번호가 공개번호라면 number_type='publication'으로 지정하십시오.")
        next_steps.append("KIPRIS 또는 공보 텍스트를 복사해 analyze_patent_document에 붙여넣을 수 있습니다.")
        return {
            "found": False,
            "requested": requested,
            "error": f"{num.label} {num.display}의 특허 정보를 확인하지 못했습니다.",
            "attempts": attempts,
            "next_steps": next_steps,
        }

    data.pop("_check", None)
    applicants = data.get("applicants") or []
    return {
        "found": True,
        "requested": requested,
        **data,
        "applicant": ", ".join(applicants) if applicants else "미확인",
        "ipc_code": (data.get("ipc_codes") or [""])[0],
        "attempts": attempts,
    }


def inspect_and_summarize_by_appno(
    patent_identifier: Annotated[str, Field(min_length=5, max_length=40)],
    number_type: NumberType = "auto",
) -> Dict[str, Any]:
    """특허번호로 원문을 조회·검증한 뒤 요약 초안과 TRL 판정 안내를 함께 만듭니다.

    Args:
        patent_identifier: 특허번호 (출원번호는 KIPRIS_API_KEY 필요)
        number_type: 번호 종류 ("auto", "application", "registration", "publication")
    """
    patent = fetch_patent_smart(patent_identifier, number_type)
    if not patent["found"]:
        return patent

    p_id = patent.get("register_number") or patent.get("application_number") or patent["requested"]["number"]
    summary = summarize_patent(
        patent_id=p_id,
        title=patent.get("title", ""),
        abstract=patent.get("abstract", ""),
        claims=patent.get("claims", []),
        applicant=patent.get("applicant"),
    )
    return {
        "metadata": {
            "source": patent["source"],
            "requested": patent["requested"],
            "application_number": patent.get("application_number"),
            "register_number": patent.get("register_number"),
            "publication_number": patent.get("publication_number"),
            "legal_status": patent.get("register_status") or "미확인",
            "ipc_codes": patent.get("ipc_codes"),
            "cpc_codes": patent.get("cpc_codes"),
            "applicant": patent.get("applicant"),
        },
        "summary": summary,
        "commercialization_trl": evaluate_commercialization(summary["technology_type"]),
    }
