"""요약서 '상용화전망'의 기술완성도 서술과 TRL 판정을 일치시키는 결정론적 검증기.

포팅 원본:
- patent-summary-wizard/supabase/functions/analyze-commercialization/trlConsistency.ts
  (classifyStage·findCommercializationSection·detectSummaryMaturity·reconcileTrl·describeTrlFromStage)
- patent-summary-wizard/src/lib/trlPresentation.ts (TRL_REFERENCE_LEVELS)
미포팅: buildScoringSummary (점수 산정 프롬프트용, MCP에서 쓰지 않음)

단계는 문장 순서가 아니라 '현재 도달한 단계'로 정한다: 과거(거쳐·이후·완료)·현재(현재·단계에 있다·진행 중)로
서술된 단계 중 가장 높은 단계를 쓰고, 목표·예정·계획 같은 미래 단계와 경쟁 기술 서술은 세지 않는다.
"""

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TrlBand:
    min: int
    max: int
    label: str


BANDS = [
    (re.compile(r"(개념\s*(?:증명|단계|수준)|원리\s*(?:수준|단계)|기초\s*연구\s*(?:수준|단계))"), TrlBand(2, 3, "기초연구")),
    (
        re.compile(
            r"(실험실(?:\s*(?:개발|연구|내|기반|차원))?\s*(?:수준|단계|규모|검증|에서)|랩\s*스케일|lab\s*scale|소규모\s*실험\s*(?:수준|단계)|실험\s*단계)",
            re.I,
        ),
        TrlBand(3, 4, "실험실"),
    ),
    (re.compile(r"(파일럿|시작품|시제품|프로토타입|실증\s*(?:단계|수준)|현장\s*(?:시험|실증|적용)\s*(?:단계|수준))"), TrlBand(5, 6, "파일럿·실증")),
    (
        re.compile(
            r"(양산\s*(?:준비|단계|가능(?!성)|체계)|즉시\s*(?:구현|적용|양산|생산)|기존\s*설비로\s*(?:바로|즉시|곧바로)?\s*(?:구현|생산|제조)|상용\s*(?:단계|수준)|시판\s*(?:중|되고))"
        ),
        TrlBand(7, 9, "양산준비"),
    ),
]

HEAD_EXCLUDED = re.compile(r"경쟁|대체\s*기술|기존\s*(?:기술|제품)|타사|해외\s*(?:업체|기업)|선진국")
HEAD_FUTURE = re.compile(r"향후|추후|앞으로|장기적|중기|단기|중장기|이후에는|[0-9]+\s*년\s*(?:내|이내|후|까지)")
HEAD_CURRENT = re.compile(r"현재|이미|지금")
TAIL_FUTURE = re.compile(
    r"목표|예정|계획|필요|요구|과제|앞두|전망|기대|향후|추후|못|않|미흡|미확보|부족|(?:확보|구축|진입|도달|전환|이행|추진|개발|달성|착수|진행)(?:할|하는\s*것|해야|하기|될)|(?:으로|로)의\s|에서는|시에는|경우"
)
TAIL_CURRENT = re.compile(
    r"현재|단계에\s*있|단계이다|단계다|수준이다|수준에\s*있|진행\s*중|진행되고|완료하고|완료했|완료하였|완료된|확보하고|확보했|확보한|보유|머물|도달했|진입했|중이다"
)
TAIL_PAST = re.compile(
    r"거쳐|거쳤|이후|마치고|마쳤|마친|검증되었|검증됐|검증을\s*완료|확인되었|확인됐|수행했|수행하였|입증|성공했|성공하였|완료|넘어|넘어선|벗어나|지나"
)
TRANSITION = re.compile(r"^(?:전환|진입|이행|넘어|나아|도약|발전|격상|올라|확대)")
CLAUSE_END = re.compile(r"(?:거쳐|거쳤고|이후|으며|하며|되며|이며|며|하고|되고|고|으나|지만|면서|는데|하여|해서)(?=\s|\Z)")
_LO_RE = re.compile(r"^\s*(?:단계|수준|규모)?\s*(?:으로|로)\s+(\S+)")
_LO_GENITIVE_RE = re.compile(r"^(?:단계|수준|규모)?\s*(?:으로|로)의")
_PASSED_RE = re.compile(r"^\s*(?:을|를)?\s*(?:넘어|넘어선|벗어나|지나)")


def classify_stage(scope: str, start: int, end: int) -> str:
    """단계 표현 하나가 current·past(도달)·future·excluded·neutral 중 무엇으로 서술됐는지 판정한다."""
    head_raw = scope[max(0, start - 14):start]
    head = head_raw[max(head_raw.rfind(c) for c in (".", "。", ",", ";", "\n")) + 1:]
    tail = scope[end:end + 32]
    stop = re.search(r"[.。,;\n]", tail)
    if stop:
        tail = tail[: stop.start()]
    cl = CLAUSE_END.search(tail)
    if cl:
        tail = tail[: cl.end()]
    lo = _LO_RE.match(tail)
    if lo and not _LO_GENITIVE_RE.match(tail.strip()):
        if TRANSITION.match(lo.group(1)):
            return "future"
        if HEAD_EXCLUDED.search(head):
            return "excluded"
        if HEAD_FUTURE.search(head):
            return "future"
        return "current"
    if HEAD_EXCLUDED.search(head):
        return "excluded"
    if _PASSED_RE.match(tail):
        return "past"
    if HEAD_FUTURE.search(head) or TAIL_FUTURE.search(tail):
        return "future"
    if HEAD_CURRENT.search(head) or TAIL_CURRENT.search(tail):
        return "current"
    if TAIL_PAST.search(tail):
        return "past"
    return "neutral"


def find_commercialization_section(summary: str) -> Optional[Dict[str, int]]:
    """상용화전망 섹션의 위치(제목 포함). 섹션이 없으면 None."""
    h = re.search(r"#{1,6}[ \t]*상용화\s*전망[^\n#]*?(?=\s|\Z)", summary) or re.search(
        r"(?:^|\n)[ \t]*\**[ \t]*상용화\s*전망[ \t]*\**[ \t]*(?=\n)", summary
    )
    if not h:
        return None
    start = h.start() + (1 if h.group(0).startswith("\n") else 0)
    body_start = h.end()
    nxt = re.search(r"(?:^|\s)#{1,6}\s", summary[body_start:])
    return {"start": start, "body_start": body_start, "end": len(summary) if not nxt else body_start + nxt.start()}


def detect_summary_maturity(summary: str) -> Optional[TrlBand]:
    """상용화전망 섹션에서 현재 도달한 기술완성도 단계를 찾는다. 섹션이 없으면 판단하지 않는다(None)."""
    if not summary:
        return None
    sec = find_commercialization_section(summary)
    if not sec:
        return None
    scope = summary[sec["body_start"]:sec["end"]]
    marked, neutral = -1, -1
    for rank, (pattern, _band) in enumerate(BANDS):
        for m in pattern.finditer(scope):
            ctx = classify_stage(scope, m.start(), m.end())
            if ctx in ("current", "past"):
                marked = max(marked, rank)
            elif ctx == "neutral":
                neutral = max(neutral, rank)
    rank = marked if marked >= 0 else neutral
    return BANDS[rank][1] if rank >= 0 else None


def _clamp_trl(trl: Any) -> int:
    try:
        value = float(trl)
    except (TypeError, ValueError):
        value = 0
    value = value if value and not math.isnan(value) else 5
    return max(1, min(9, math.floor(value + 0.5)))  # JS Math.round


def reconcile_trl(trl: Any, summary: str) -> Dict[str, Any]:
    """TRL이 서술 단계 범위를 벗어나면 범위 안으로 보정한다. changed=True면 근거문도 다시 써야 한다."""
    t = _clamp_trl(trl)
    band = detect_summary_maturity(summary)
    if not band:
        return {"trl": t, "changed": False, "band": None}
    fixed = max(band.min, min(band.max, t))
    return {"trl": fixed, "changed": fixed != t, "band": band}


NEXT_STEP = {
    1: "핵심 원리에 대한 단편 실험 데이터가 확보되어야 다음 단계로 진입할 수 있다.",
    2: "단편 실험 데이터가 확보되어야 다음 단계로 진입할 수 있다.",
    3: "실험실 수준의 정량 데이터가 누적되어야 4단계로 진입할 수 있다.",
    4: "모사 환경의 통합 실시예가 보강되면 5단계로 진입 가능하다.",
    5: "파일럿·시작품 단계의 현장 적용 사례가 추가되면 6단계로 올라설 수 있다.",
    6: "실환경 운영 데이터가 누적되어야 상용화 단계인 7로 진입할 수 있다.",
    7: "기존 설비 기반의 안정적 양산·유통 근거가 확보되면 8단계로 인정 가능하다.",
    8: "동일 형태의 시판이 확인되면 9단계로 평가된다.",
    9: "동일 형태의 시판·유통이 이어지는 상용화 완료 단계로 본다.",
}


def describe_trl_from_stage(trl: Any, band: TrlBand) -> str:
    """보정된 TRL의 근거문. 원문에 없는 근거를 단정하지 않고 요약서의 서술 단계를 밝힌다."""
    t = _clamp_trl(trl)
    josa = "으로" if t in (3, 6) else "로"
    return f"요약서 상용화전망이 기술완성도를 '{band.label}' 단계로 서술하고 있어 TRL {t}{josa} 판단되며, {NEXT_STEP[t]}"


# trlPresentation.ts — 표시용 용어 (TRL 점수를 바꾸지 않음)
TRL_REFERENCE_LEVELS: List[Dict[str, Any]] = [
    {"level": 1, "label": "기초이론 정립", "description": "기초 이론·실험", "example": "현상·원리 발견"},
    {"level": 2, "label": "기술개념 정립", "description": "실용 목적의 아이디어·특허 등 개념 정립", "example": "용도 착안, 출원 직전"},
    {"level": 3, "label": "개념 실증", "description": "연구실 규모의 기본성능 검증", "example": "추출물 활성 1차 확인"},
    {"level": 4, "label": "실험실 검증", "description": "연구실 규모의 핵심성능 평가", "example": "세포 수준 효능, 마커·프라이머 실험실 검증"},
    {"level": 5, "label": "시제품 성능 평가", "description": "확정된 시작품 제작 및 성능 평가", "example": "동물모델 효능, 최적 공정조건 확정, 표준 PCR 조건 확립"},
    {"level": 6, "label": "파일럿 실증", "description": "파일럿 규모 시작품 제작 및 성능 평가", "example": "파일럿 추출·시제품 현장 테스트, 장치 실증"},
    {"level": 7, "label": "신뢰성 검증", "description": "신뢰성 평가 및 수요기업 평가", "example": "임상(반려견 등)·실사용 환경 검증, 수요처 평가"},
    {"level": 8, "label": "인증·표준화", "description": "시제품 인증 및 표준화", "example": "KC 인증, 기능성 원료 인정, 표준 검사법 등재"},
    {"level": 9, "label": "사업화", "description": "사업화", "example": "양산·판매 중"},
]


def reference_levels(lo: int, hi: int) -> List[Dict[str, Any]]:
    return [lvl for lvl in TRL_REFERENCE_LEVELS if lo <= lvl["level"] <= hi]
