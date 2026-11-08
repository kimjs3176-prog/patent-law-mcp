"""청구항 텍스트 공통 처리 유틸리티

요약·권리범위 매칭·번들링 도구가 같은 기준으로 청구항을 해석하도록
독립항/종속항 판별, 삭제 청구항 판별, 구성요소 분해, 기술 유형 판별을 한곳에 모았습니다.
"""

import re
from typing import List, Tuple

_DEPENDENT_RE = re.compile(
    r"(?:제\s*\d+\s*항|청구항\s*\d+)[^.;]{0,40}?(?:에\s*있어서|에\s*따른|에\s*의한|중\s*어느)"
)

_DEPENDENT_EN_RE = re.compile(r"\b(?:of|in|to|according to|as claimed in|as recited in|as defined in)\s+claims?\s+\d+", re.I)
_TRANSITION_EN_RE = re.compile(
    r"\b(?:comprising|consisting essentially of|consisting of|including|which comprises|characterized in that|wherein)\b\s*:?", re.I
)


def is_english(text: str) -> bool:
    letters = re.findall(r"[A-Za-z가-힣]", text or "")
    return bool(letters) and sum(1 for ch in letters if ch.isascii()) / len(letters) > 0.6


_TRANSITION_RE = re.compile(
    r"[;；]?\s*(?:을|를)?\s*(?:포함하여\s*이루어지는|포함하는|포함하고|구비하는|구비한)"
    r"|(?:으로|로)\s*(?:이루어진|이루어지는|구성된|구성되는)"
)

METHOD_WORDS = ("방법", "공정", "제조법", "method", "process")
APPARATUS_WORDS = ("장치", "시스템", "모듈", "기기", "센서", "설비", "기구", "apparatus", "system", "device", "machine", "assembly")
COMPOSITION_WORDS = ("조성물", "화합물", "추출물", "균주", "제제", "소재", "composition", "compound", "extract", "strain", "formulation")

TECH_TYPE_LABELS = {
    "method": "공정 및 제조방법 (Process/Method)",
    "apparatus": "장치 및 시스템 (Apparatus/System)",
    "composition": "바이오·화학 소재 및 조성물 (Composition/Bio)",
    "mixed": "물건·방법 복합 (Product + Method)",
    "product": "물건 (Product)",
}


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_deleted_claim(claim: str) -> bool:
    c = normalize_ws(claim).strip("().[] ")
    return c == "삭제" or (len(c) <= 6 and "삭제" in c)


def is_dependent_claim(claim: str) -> bool:
    head = normalize_ws(claim)[:80]
    return bool(_DEPENDENT_RE.search(head) or _DEPENDENT_EN_RE.search(head))


def split_claim_elements(claim: str) -> Tuple[List[str], str]:
    """청구항을 (구성요소 목록, 청구 대상)으로 분해합니다.

    예) "A; B; 및 C;를 포함하는 선별 장치." -> (["A", "B", "C"], "선별 장치")
    전환부("~를 포함하는") 뒤의 청구 대상은 구성요소로 보지 않습니다.
    """
    text = normalize_ws(claim)
    if is_english(text):
        # 영문: 전제부 + 전환부(comprising 등) + 구성요소 — 한국어와 순서가 반대
        text = re.sub(r"^\d+\s*[.)]\s*", "", text)
        m = _TRANSITION_EN_RE.search(text)
        subject, body = (text[: m.start()].strip(" ,"), text[m.end():]) if m else ("", text)
        subject = re.sub(r"^(?:an?|the)\s+", "", subject, flags=re.I)
        parts = [re.sub(r"^(?:and|or)\s+", "", p.strip(" ,.")) for p in re.split(r";", body)]
        return [p for p in parts if len(p) >= 2], subject
    matches = list(_TRANSITION_RE.finditer(text))
    if matches:
        last = matches[-1]
        body = text[: last.start()]
        subject = text[last.end():].strip(" .")
    else:
        body, subject = text, ""

    parts = []
    for p in re.split(r"[;；]", body):
        p = re.sub(r"^(?:및|또는)\s+", "", p.strip(" ,"))
        if len(p) >= 2:
            parts.append(p)
    return parts, subject


def _classify_title_part(part: str) -> str:
    if is_english(part):
        low = part.lower()
        for kind, words in (("method", METHOD_WORDS), ("apparatus", APPARATUS_WORDS), ("composition", COMPOSITION_WORDS)):
            if any(re.search(rf"\b{w}\b", low) for w in words if w.isascii()):
                return kind
        return "product"
    words = part.strip().split()
    last = words[-1] if words else ""
    if any(k in last for k in METHOD_WORDS):
        return "method"
    if any(k in last for k in COMPOSITION_WORDS):
        return "composition"
    if any(k in last for k in APPARATUS_WORDS):
        return "apparatus"
    return "product"


def detect_technology_kind(title: str, main_claim: str = "") -> str:
    """발명의 명칭(없으면 청구항 1의 청구 대상)으로 기술 유형 키를 판별합니다.

    "~장치 및 ~방법"처럼 물건과 방법이 함께 청구된 경우 'mixed'를 반환합니다.
    """
    source = (title or "").strip()
    if not source and main_claim:
        _, subject = split_claim_elements(main_claim)
        source = subject or normalize_ws(main_claim)[-30:]
    if not source:
        return "product"

    kinds = {_classify_title_part(p) for p in re.split(r"\s+및\s+|\s+and\s+|,\s*", source, flags=re.I) if p.strip()}
    if "method" in kinds and len(kinds) > 1:
        return "mixed"
    for k in ("method", "apparatus", "composition"):
        if k in kinds:
            return k
    return "product"


def detect_technology_type(title: str, main_claim: str = "") -> str:
    return TECH_TYPE_LABELS[detect_technology_kind(title, main_claim)]
