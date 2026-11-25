"""기술사업화 평가(기술성·시장성·사업성 점수, V-RAY 사업성 보정, 문구 정합성) 결정론적 규칙.

포팅 원본: patent-summary-wizard/supabase/functions/analyze-commercialization/index.ts (SCORE_VERSION s2-2026-11)
- 체크리스트(상세 채점 프롬프트의 T·M·B 가감점, 상한 95·하한 55)와 총점 가중치(0.35·0.35·0.30)
- TRL 판정 기준표(2~9단계)
- stageFromTrl·vrayBusinessIndex(V-RAY 사업화 실행성 지수)와 사업성 결합(체크리스트 60% + 지수 40%)
- enforceConsistency·softenIfOverclaim·upliftIfUnderclaim(점수-문구 정합성)
- strip*Mentions·normalizeReason·normalizeAnalysis·make*Fallback(문구 후처리·기본 문구)
- 점수 구간별 결론 문장 규칙

원본에서는 LLM이 체크리스트를 채점했다. MCP에서는 Claude가 충족 항목과 근거만 고르고, 점수 합산과 보정은 여기서 계산한다.
JS의 Math.round는 반올림(0.5 올림)이라 _js_round로 맞춘다.

원본과 다르게 고친 점 (산출물 점검 2026-11-25):
- 기술성 기본 문구에서 점수 숫자('68점의')를 빼고, 60~69점 문구의 '다소 미흡'을 없앰 (등급 '보통'과 어긋남)
- 기본 문구에도 점수 구간 결론 문장을 붙여 등급과 결론이 항상 일치
- 점수·TRL 문장을 지운 뒤 문장이 깨지거나 합쇼체이면 기본 문구로 대체 (원본은 지우기 전에만 검사)
- 종합 의견 기본 문구에서 기술·시장이 모두 약할 때 '~지만'으로 잇지 않음
- 기술성 기본 문구의 조사를 앞 단어 받침에 맞춤 ('실시예은' → '실시예는')
"""

import math
import re
from datetime import date
from typing import Any, Dict, List, Optional

SCORE_VERSION = "s2-2026-11"
BASE = 60
FLOOR, CAP = 55, 95
WEIGHTS = {"technology": 0.35, "market": 0.35, "business": 0.30}
AXIS_LABEL = {"technology": "기술성", "market": "시장성", "business": "사업성"}

# (id, 축, 가감점, 그룹, 기준) — 원본 상세 채점 프롬프트 그대로
CHECKLIST: List[Dict[str, Any]] = [
    {"id": "T-A1", "axis": "technology", "points": 8, "group": "A. 독립항의 차별성", "text": "독립항이 선행기술 대비 새로운 구성요소·작용원리·결합관계를 명확히 제시"},
    {"id": "T-A2", "axis": "technology", "points": 5, "group": "A. 독립항의 차별성", "text": "실시예·실험데이터·비교예로 진보성을 뒷받침"},
    {"id": "T-A3", "axis": "technology", "points": 3, "group": "A. 독립항의 차별성", "text": "단순 파라미터 조정·치환을 넘는 구조적 차별성 존재"},
    {"id": "T-A4", "axis": "technology", "points": -5, "group": "A. 독립항의 차별성", "text": "공지기술의 단순 조합·치환 수준으로 판단되거나 진보성 서술 전무"},
    {"id": "T-B1", "axis": "technology", "points": 6, "group": "B. 권리범위의 넓이", "text": "독립항이 상위개념(기능적·일반화된 표현)으로 작성되어 다양한 변형·등가물 포괄"},
    {"id": "T-B2", "axis": "technology", "points": 4, "group": "B. 권리범위의 넓이", "text": "종속항이 구성요소·범위·조건의 변형(수치범위·재료군·공정조건)을 폭넓게 커버"},
    {"id": "T-B3", "axis": "technology", "points": 3, "group": "B. 권리범위의 넓이", "text": "IPC 서브클래스 2개 이상(다분야 적용 가능성)"},
    {"id": "T-B4", "axis": "technology", "points": -5, "group": "B. 권리범위의 넓이", "text": "독립항이 특정 제품·수치·재료에 좁게 한정되어 회피 여지 큼"},
    {"id": "T-C1", "axis": "technology", "points": 6, "group": "C. 회피설계 가능성", "text": "핵심 구성요소가 필수불가결(대체수단이 제한적)하여 우회 곤란"},
    {"id": "T-C2", "axis": "technology", "points": 4, "group": "C. 회피설계 가능성", "text": "작용원리·메커니즘 자체가 청구되어 대체 구현 곤란"},
    {"id": "T-C3", "axis": "technology", "points": -5, "group": "C. 회피설계 가능성", "text": "비핵심 파라미터·부수적 구성만 청구되어 단순 변경으로 회피 가능"},
    {"id": "T-C4", "axis": "technology", "points": -3, "group": "C. 회피설계 가능성", "text": "균등론 적용 여지가 좁은 좁은 한정 표현 다수"},
    {"id": "M1", "axis": "market", "points": 5, "group": "시장성", "text": "IPC 메인그룹이 소비재/식품/생활용품/농축산물(A21~A24, A01, A47 등)"},
    {"id": "M2", "axis": "market", "points": 5, "group": "시장성", "text": "동일 카테고리에 이미 유통 중인 유사 제품군 존재(떡·빵·음료·면·발효식품·기능성식품 등)"},
    {"id": "M3", "axis": "market", "points": 5, "group": "시장성", "text": "복수 산업·복수 용도 적용 가능(IPC 다른 섹션 2개 이상)"},
    {"id": "M4", "axis": "market", "points": 5, "group": "시장성", "text": "수요처가 일반 소비자(B2C)로 명확"},
    {"id": "M5", "axis": "market", "points": 5, "group": "시장성", "text": "차별적 우위(천연·친환경·기능성·간편화 등)가 본문에 구체 서술"},
    {"id": "M6", "axis": "market", "points": 5, "group": "시장성", "text": "농가·중소기업이 직접 활용 가능한 응용 제품"},
    {"id": "M7", "axis": "market", "points": -5, "group": "시장성", "text": "적용 산업이 단일·협소"},
    {"id": "M8", "axis": "market", "points": -5, "group": "시장성", "text": "차별점이 본문에 드러나지 않음"},
    {"id": "B1", "axis": "business", "points": 5, "group": "사업성", "text": "기존 설비·공정으로 구현 가능"},
    {"id": "B2", "axis": "business", "points": 5, "group": "사업성", "text": "제조방법 단계가 본문에 구체적으로 기술"},
    {"id": "B3", "axis": "business", "points": 5, "group": "사업성", "text": "원료·재료가 시중 조달 가능"},
    {"id": "B4", "axis": "business", "points": 5, "group": "사업성", "text": "인허가·규제 장벽이 낮은 식품/생활용품 범주"},
    {"id": "B5", "axis": "business", "points": 5, "group": "사업성", "text": "라이선싱·기술이전 수요가 명확한 농가/중소기업 대상"},
    {"id": "B6", "axis": "business", "points": 5, "group": "사업성", "text": "양산 시 단가 경쟁력 또는 초기 투자 규모가 작음"},
    {"id": "B7", "axis": "business", "points": -5, "group": "사업성", "text": "고가 특수설비·임상시험 등 진입장벽 큰 분야"},
    {"id": "B8", "axis": "business", "points": -5, "group": "사업성", "text": "후속 R&D가 추가로 크게 필요"},
]
CHECKLIST_BY_ID = {c["id"]: c for c in CHECKLIST}

# TRL 결정론적 판정 기준 (충족되는 가장 높은 단계 하나, 출원 경과연수 미반영)
TRL_RULES = {
    2: "개념·원리만 서술, 실험 전무",
    3: "핵심 원리에 대한 단편적 실험·시뮬레이션 1건",
    4: "실험실 수준 데이터(수치·표) 다수, 구성요소 검증",
    5: "모사 환경에서의 통합 실험·실시예 다수",
    6: "실증·파일럿·시작품 명시(현장·필드 적용 사례)",
    7: "실환경 운영 데이터 또는 상용화 언급",
    8: "제조방법·실시예가 구체적이고 기존 설비로 즉시 구현 가능, 또는 이미 유통 중인 카테고리(떡·빵·음료·면·발효식품·기능성식품·가공식품 등)",
    9: "본 특허 기술이 동일 형태로 시판·유통 중임이 명확",
}

# 점수 구간별 결론 문장 (reason 3종의 마지막 문장)
CONCLUSIONS = {
    "우수": ("우수한 수준으로 평가된다.", "높은 가능성을 보유한 것으로 평가된다."),
    "보통": ("보통 수준으로 평가된다.",),
    "미흡": ("다소 미흡한 수준으로 평가된다.", "보완이 필요한 수준으로 평가된다."),
}

WRITING_RULES = [
    "technology/market/business 근거는 정확히 2문장: (1) 본문에서 확인된 근거와 정성적 판단 → (2) 상위 평가를 위한 보완점",
    "근거 문장에 점수 숫자·'~점대'·'~점이다', TRL·성숙도, 존속기간·잔여기간·만료 언급 금지 (도구가 지움)",
    "기술성 근거는 A 차별성·B 권리범위·C 회피설계 관점만, 청구항 '개수'는 근거로 쓰지 않음. 초록 복사 어투('본 발명은…') 금지",
    "사업성 근거에 발명·조성물 구성 설명 금지, 시장성 근거에 시장규모 등 문서 밖 데이터 금지",
    "기술성·시장성·사업성 근거의 마지막 문장은 점수 구간 결론으로 끝냄: 80점 이상 '우수한 수준으로 평가된다.'/'높은 가능성을 보유한 것으로 평가된다.', "
    "60~79점 '보통 수준으로 평가된다.', 60점 미만 '다소 미흡한 수준으로 평가된다.'/'보완이 필요한 수준으로 평가된다.' (아니면 도구가 결론 문장을 덧붙임)",
    "TRL 근거는 1문장, 'TRL n으로 판단된다' 또는 'TRL n 수준이다'를 포함",
    "종합 의견(analysis)은 요약서를 압축한 정확히 2문장 (강점·활용 가능성 / 유의점·기대효과)",
    "모든 문장은 해라체('~다.')로 끝내고 합쇼체('~합니다') 금지",
    "강한 긍정 표현('우수·탁월·광범위·수요 명확' 등)은 그 항목을 80점 이상으로, 최상급('매우 우수·독보적' 등)은 85점 이상으로 올림 — 점수에 맞는 어조로 쓸 것",
]


def _js_round(x: float) -> int:
    return math.floor(x + 0.5)


def clamp_score(v: float) -> int:
    return max(FLOOR, min(CAP, int(v)))


def grade(score: int) -> str:
    return "우수" if score >= 80 else "보통" if score >= 60 else "미흡"


# ---------------------------------------------------------------- V-RAY
def stage_from_trl(trl: int) -> Dict[str, Any]:
    if trl <= 2:
        return {"name": "기초연구", "lead": 4, "immature_premium": 0.328}
    if trl <= 4:
        return {"name": "실험", "lead": 3, "immature_premium": 0.241}
    if trl <= 6:
        return {"name": "시제품", "lead": 2, "immature_premium": 0.153}
    if trl <= 8:
        return {"name": "실용화", "lead": 1, "immature_premium": 0.066}
    return {"name": "양산", "lead": 0, "immature_premium": 0}


def parse_patent_date(value: Optional[str]) -> Optional[date]:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def assess_patent_term(filing_date: Optional[str], as_of: date) -> Dict[str, Any]:
    filed = parse_patent_date(filing_date)
    if not filed:
        return {"elapsed_years": None, "remaining_years": None, "level": "판단 불가"}
    elapsed = max(0.0, (as_of - filed).days / 365.25)
    remaining = max(0.0, 20 - elapsed)
    level = "충분" if remaining >= 12 else "보통" if remaining >= 7 else "짧음" if remaining > 0 else "만료 추정"
    return {"elapsed_years": elapsed, "remaining_years": remaining, "level": level}


def vray_business_index(
    trl: int,
    as_of: date,
    filing_date: Optional[str] = None,
    registration_number: Optional[str] = None,
    registration_date: Optional[str] = None,
    ipc_count: int = 0,
    abstract_len: int = 0,
) -> Dict[str, Any]:
    stage = stage_from_trl(trl)
    maturity = max(0.0, min(1.0, 1 - stage["lead"] / 4))
    registered = bool(registration_number and len(str(registration_number)) > 4) or bool(registration_date)
    validity = 0.95 if registered else 0.65
    if abstract_len >= 300:
        validity += 0.03
    elif 0 < abstract_len < 80:
        validity -= 0.05
    validity = max(0.3, min(1.0, validity))
    term = assess_patent_term(filing_date, as_of)
    remaining = term["remaining_years"] if term["remaining_years"] is not None else 20
    life_ratio = max(0.0, min(1.0, remaining / 15))
    breadth = max(0.0, min(1.0, ipc_count / 3))
    composite = maturity * 0.35 + validity * 0.25 + life_ratio * 0.2 + breadth * 0.2
    index = _js_round(55 + 40 * composite)
    return {
        "index": max(55, min(95, index)),
        "parts": {
            "maturity": _js_round(maturity * 100) / 100,
            "validity": _js_round(validity * 100) / 100,
            "life_ratio": _js_round(life_ratio * 100) / 100,
            "breadth": _js_round(breadth * 100) / 100,
            "remaining_years": remaining,
            "lead": stage["lead"],
        },
        "stage": stage["name"],
        "registered": registered,
        "term_known": term["remaining_years"] is not None,
    }


def blend_business(checklist_score: int, vray_index: int) -> int:
    return max(55, min(95, _js_round(checklist_score * 0.6 + vray_index * 0.4)))


def total_score(t: int, m: int, b: int) -> int:
    return _js_round(t * 0.35 + m * 0.35 + b * 0.3)


# ---------------------------------------------------------------- 점수-문구 정합성
STRONG_TOP = re.compile(r"(매우\s*우수|매우\s*뛰어|독보적|독보|최고|최상|광범위한|매우\s*광범|시장\s*검증\s*완료|즉시\s*상용)")
STRONG_POS = re.compile(
    r"(우수|뛰어|탁월|광범위|높은\s*경쟁력|차별적\s*우위|검증된\s*시장|수요[가\s]*명확|높은\s*확장|상용화\s*용이|즉시\s*적용|"
    r"구현\s*가능성[이가]?\s*(?:매우\s*)?높|완성도[가이]?\s*(?:매우\s*)?높|차별성[이가]?\s*(?:매우\s*)?높|확장성[이가]?\s*(?:매우\s*)?높|"
    r"상용화\s*가능성[이가]?\s*(?:매우\s*)?높|기술[적성]?\s*완성도[가이]?\s*(?:매우\s*)?높)"
)


def enforce_consistency(score: int, reason: str) -> int:
    if not reason:
        return score
    if STRONG_TOP.search(reason) and score < 85:
        return 85
    if STRONG_POS.search(reason) and score < 80:
        return 80
    return score


def soften_if_overclaim(score: int, reason: str) -> str:
    if not reason or score >= 78:
        return reason
    out = reason
    out = re.sub(r"매우\s*(높|우수|뛰어|탁월|광범위)", r"어느 정도 \1", out)
    out = re.sub(r"(독보적|탁월|최상|최고)(이|인|이며|이고|이다|하다)?", r"양호\2", out)
    out = re.sub(r"광범위(하|한|하게|하다)", r"일정 범위\1", out)
    out = re.sub(
        r"(구현\s*가능성|완성도|차별성|확장성|상용화\s*가능성|경쟁력|시장성|사업성|기술성)([이가])?\s*(매우\s*)?높다",
        r"\1은 보통 수준이다",
        out,
    )
    out = re.sub(r"(우수|탁월)하다", "양호하다", out)
    out = re.sub(r"(뛰어나다|뛰어남)", "안정적이다", out)
    if score < 60:
        out = out.replace("양호하다", "보완이 필요하다")
        out = re.sub(r"보통\s*수준이다", "미흡한 수준이다", out)
    return out


def uplift_if_underclaim(score: int, reason: str) -> str:
    if not reason or score < 80:
        return reason
    out = re.sub(r"미흡한\s*수준이다", "양호한 수준이다", reason)
    out = re.sub(r"부족한\s*편이다", "어느 정도 갖춰진 편이다", out)
    out = re.sub(r"(보완이\s*필요하다)(?=[\s.])", "추가 보강의 여지가 있다", out)
    return out


# ---------------------------------------------------------------- 문구 후처리
def clean_korean_text(value: Any) -> str:
    t = re.sub(r"\s+", " ", str(value or ""))
    t = re.sub(r"^[①-⑨0-9]+[).]\s*", "", t)
    t = re.sub(r"^(강점|제언|분석|근거|평가|의견)\s*[:：-]\s*", "", t)
    return t.strip()


def is_incomplete_sentence(value: Any) -> bool:
    text = clean_korean_text(value)
    if not text or len(text) < 18:
        return True
    if re.search(r"[,(·•및와과의로]$", text):
        return True
    if re.search(r"(이며|하고|또는|및|으로|에서|하는|된|되어|통해|위해|관련된|필요한)$", text):
        return True
    return not re.search(r"(다|된다|있다|없다|필요하다|판단된다|기대된다|관건이다|수준이다)[.!?。]?$", text)


def ensure_complete_sentence(value: Any, fallback: str) -> str:
    text = clean_korean_text(value)
    if is_incomplete_sentence(text):
        return fallback
    return text if re.search(r"[.!?。]$", text) else f"{text}."


def looks_like_patent_summary(value: Any) -> bool:
    text = clean_korean_text(value)
    summary_tone = re.search(
        r"(본\s*발명|에\s*관한\s*것|포함한다|포함하는|유효성분|분리하였|확인하였|확인되었|화합물인|계열\s*화합물|NO\s*생성|조성물|방법이다|특허\s*기능)",
        text,
    )
    evaluation_tone = re.search(
        r"(근거|검증|차별|진보|구체|제한|보완|상용|사업|시장|평가|판단|수준|장벽|실증|데이터|리스크|청구항\s*구체성|재현성)", text
    )
    return bool(summary_tone) and not evaluation_tone


def normalize_reason(value: Any, fallback: str) -> str:
    if looks_like_patent_summary(value) or is_incomplete_sentence(value):
        return fallback
    return ensure_complete_sentence(value, fallback)


HONORIFIC_RE = re.compile(r"(?:습니다|입니다|됩니다|합니다)[.!?。]?(?:\s|$)")
_SENTENCE_RE = re.compile(r"[^.!?。]+[.!?。]+")


def normalize_analysis(value: Any, fallback: str) -> str:
    text = clean_korean_text(value)
    if is_incomplete_sentence(text) or len(re.findall(r"[.!?。]", text)) < 2:
        return fallback
    sentences = _SENTENCE_RE.findall(text)
    if len(text) > 220 and len(sentences) >= 2:
        text = " ".join(sentences[:2]).strip()
    sentences = _SENTENCE_RE.findall(text)
    if len(sentences) > 2:
        text = " ".join(sentences[:2])
    return ensure_complete_sentence(text, fallback)


def strip_trl_mentions(text: str) -> str:
    if not text:
        return text
    out = re.sub(r"(?:^|\s)(?:이는\s*|따라서\s*|그래서\s*)?TRL\s*[0-9]+\s*[^.。!?]*[.。!?]", "", text)
    out = re.sub(r"\s*TRL\s*[0-9]+\s*(?:수준|단계|에\s*해당하는|으로\s*판단되며|이며)?[^.,。!?]*", "", out)
    out = re.sub(r"TRL\s*[0-9]+", "", out, flags=re.I)
    return re.sub(r"\s+([,.。!?])", r"\1", re.sub(r"\s{2,}", " ", out)).strip()


def strip_score_mentions(s: Optional[str]) -> str:
    if not s:
        return s or ""
    out = re.sub(
        r"(?:,?\s*(?:그래서|따라서|이에|결과적으로|종합하면|이로써))?\s*[가-힣]{0,8}(?:성|점수)?(?:은|는|이|가)?\s*\(?[0-9]{2,3}\)?\s*점대?로?\s*(?:평가|산출|판단|분류|책정)(?:된다|되며|되어|됨)\.?",
        "",
        s,
    )
    out = re.sub(r"\s*[0-9]{2,3}\s*점(?:대|이다|으로|에)\s*[가-힣]{0,8}(?:평가된다|산출된다|판단된다|책정된다|된다)?\.?", "", out)
    out = re.sub(r"총점[은이]?\s*[0-9]{2,3}\s*점\.?", "", out)
    out = re.sub(r"\b[0-9]{2,3}\s*점대\b", "", out, flags=re.ASCII)
    out = re.sub(r"\.{2,}", ".", re.sub(r"\s+([.,])", r"\1", re.sub(r"\s{2,}", " ", out))).strip()
    return re.sub(r",\s*$", ".", out)


_DURATION_RE = re.compile(r"(존속기간|잔여\s*(?:보호)?기간|잔존(?:권리)?기간|경과\s*(?:연수|기간|년)|만료|보호기간)")


def strip_duration_mentions(text: str) -> str:
    if not text:
        return text
    sentences = re.split(r"(?<=[.。!?])\s*", text)
    kept = [s for s in sentences if s.strip() and not _DURATION_RE.search(s.strip())]
    if not kept:
        return text.strip()
    out = re.sub(r"\s+([,.。!?])", r"\1", re.sub(r"\s{2,}", " ", " ".join(kept))).strip()
    return re.sub(r",\s*$", ".", out)


# ---------------------------------------------------------------- 기본 문구 (원본 make*Fallback)
def josa(word: str, with_batchim: str, without: str) -> str:
    """앞 단어의 받침에 맞는 조사 (원본은 '이/은'을 고정해 '실시예은'처럼 틀렸다)."""
    last = word.strip()[-1:] if word.strip() else ""
    if "가" <= last <= "힣":
        return with_batchim if (ord(last) - 0xAC00) % 28 else without
    return with_batchim


def make_technology_fallback(score: int, claims_count: int, has_data: bool, multi_ipc: bool) -> str:
    claim_part = (
        f"청구항 {claims_count}건의 권리 범위" if claims_count >= 10 else f"청구항 {claims_count}건" if claims_count >= 5 else "제한된 청구항 구성"
    )
    data_part = "실험 수치 기반의 검증 근거" if has_data else "원리 중심의 실시예"
    ipc_part = "와 복수 IPC 적용성" if multi_ipc else ""
    evidence = f"{claim_part}, {data_part}{ipc_part}"
    if score >= 85:
        return f"{evidence}{josa(evidence, '이', '가')} 폭넓게 확인돼 기술 완성도가 분명히 드러나며, 이러한 근거가 결합돼 높은 평가로 이어진다. 다만 후속 비교 실험과 재현 데이터가 더해지면 권리 범위와 진보성을 한층 견고하게 다질 수 있다."
    if score >= 78:
        return f"{evidence}{josa(evidence, '이', '가')} 함께 확인돼 기술적 완결성이 어느 정도 갖춰진 편이며, 그 흐름이 양호한 평가로 이어진다. 다만 선행기술과의 차별성을 더 선명히 보여줄 비교 실험과 재현 데이터가 보완되면 상위 점수대까지 노려볼 수 있다."
    if score >= 70:
        return f"{evidence}{josa(evidence, '은', '는')} 확인되지만 차별성과 재현성을 뒷받침할 근거가 다소 제한적이라 보통 수준에 머문다. 비교예와 진보성 서술이 구체화되어야 상위 점수대로 올라설 수 있다."
    if score >= 60:
        return f"{claim_part}{josa(claim_part, '과', '와')} {data_part}만으로는 기술 완성도를 단정하기 어렵다. 비교예 확보와 반복 실험, 진보성 서술 보완이 함께 이뤄져야 점수 상향을 기대할 수 있다."
    return "청구항과 실시예의 깊이가 얕아 기술적 근거가 충분히 드러나지 않으며, 그 결과 낮은 수준에 그친다. 비교 실험, 재현 데이터, 진보성 서술이 모두 보강되어야 의미 있는 평가가 가능하다."


def make_market_fallback(score: int) -> str:
    if score >= 85:
        return "적용 산업과 수요처가 명확히 드러나고 차별적 우위가 본문에 충분히 서술돼 시장 진입 매력이 높은 편이다. 실제 구매 주체와 경쟁 대체재 분석이 더해지면 초기 수요 검증과 보급 전략을 더 설득력 있게 제시할 수 있다."
    if score >= 78:
        return "적용 산업과 수요처가 어느 정도 구체화돼 있고 차별적 우위도 본문에서 확인되어 시장 진입 가능성이 양호하다. 다만 실구매 수요, 운영 비용, 기존 방제·관리 방식 대비 전환 이익을 보강하면 확산 논리가 더 분명해진다."
    if score >= 70:
        return "관련 산업 적용성은 확인되지만 수요 규모와 차별적 구매 요인이 제한적으로 제시되어 시장성은 보통 수준이다. 목표 수요처를 공공기관·농가·서비스 사업자 등으로 좁히고 대체 솔루션 대비 효익을 수치화해야 한다."
    if score >= 60:
        return "적용처가 다소 협소하고 수요 근거가 약해 시장 진입 논리가 아직 충분하지 않다. 활용 시나리오, 구매 의사, 경쟁 대체재 대비 비용 절감 효과를 함께 제시해야 사업화 설득력이 높아진다."
    return "적용처와 수요 근거가 거의 드러나지 않아 시장성 판단에 필요한 기반 정보가 부족하다. 목표 고객, 반복 구매 가능성, 대체재 대비 차별적 효익을 구체화해야 의미 있는 시장 평가가 가능하다."


def make_business_fallback(score: int) -> str:
    if score >= 85:
        return "기존 설비·공정 활용 여지가 분명하고 인허가 장벽이 낮은 영역이라 사업화 실행성이 높다. 기술이전 조건, 초기 수요처, 운영·유지보수 체계가 정리되면 빠른 실증과 보급형 상용화 흐름까지 기대할 수 있다."
    if score >= 78:
        return "기존 설비 활용성과 낮은 인허가 장벽이 함께 확인되어 사업화 추진 여건은 양호한 편이다. 기술이전 조건, 파일럿 운영 비용, 초기 구매처 확보 전략이 마무리되면 상용화 속도를 한층 높일 수 있다."
    if score >= 70:
        return "구현 가능성은 확인되지만 양산 조건과 투자회수 근거가 아직 제한적이어서 사업성은 보통 수준이다. 파일럿 단가 검증, 유지보수 방식, 라이선싱 수요 구체화가 후속 사업화의 핵심 보완점이다."
    if score >= 60:
        return "공정·비용·수요처 근거가 다소 약해 사업화 실행 계획을 바로 확정하기는 어렵다. 후속 실증, 기술이전 패키지, 단가 경쟁력 분석이 함께 보완되어야 실제 도입 가능성이 높아진다."
    return "구현 조건과 사업화 근거가 충분히 드러나지 않아 사업성 판단에 필요한 실행 정보가 부족하다. 파일럿 검증, 단가 경쟁력 분석, 기술이전 전략이 모두 갖춰져야 의미 있는 사업화 평가가 가능하다."


def make_trl_fallback(trl: int) -> str:
    if trl <= 2:
        return f"원리·개념 서술 중심으로 실험 검증 근거가 확인되지 않아 TRL {trl}로 판단되며, 단편 실험 데이터가 확보되어야 다음 단계로 진입할 수 있다."
    return {
        3: "핵심 원리에 대한 단편 실험은 확인되지만 반복 데이터와 구성요소 검증이 부족해 TRL 3으로 판단되며, 실험실 수준의 정량 데이터 누적이 필요하다.",
        4: "실험실 수준의 수치 데이터와 구성요소 검증이 확인돼 TRL 4로 판단되며, 모사 환경의 통합 실시예가 보강되면 5단계로 진입 가능하다.",
        5: "모사 환경에서의 통합 실시예와 복수 구성 검증이 확인돼 TRL 5로 판단되며, 파일럿·시작품 단계의 현장 적용 사례가 추가되면 6단계로 올라설 수 있다.",
        6: "시작품·파일럿 또는 현장 적용 사례가 제시돼 TRL 6으로 판단되며, 실환경 운영 데이터가 누적되어야 상용화 단계인 7로 진입할 수 있다.",
        7: "실환경 적용 또는 상용화 언급이 확인돼 TRL 7로 판단되며, 기존 설비 기반의 안정적 양산·유통 근거가 확보되면 8단계로 인정 가능하다.",
        8: "제조방법과 실시예가 구체적이고 기존 설비로 즉시 구현 가능한 수준이어서 TRL 8로 판단되며, 동일 형태의 시판이 확인되면 9단계로 평가된다.",
    }.get(trl, "본 기술이 동일 형태로 시판·유통되는 근거가 확인돼 상용화 완료 단계인 TRL 9로 판단된다.")


def make_analysis_fallback(t: int, m: int, b: int) -> str:
    tech = "기술 검증 근거는 양호하고" if t >= 80 else "기술 근거는 일부 확보됐지만" if t >= 70 else "기술 근거는 보완이 필요하지만"
    if t < 70 and m < 80:  # 둘 다 약하면 '~지만'으로 잇지 않는다
        tech = "기술 근거는 보완이 필요하고"
    market = "시장 적용성은 기대된다" if m >= 80 else "시장 적용성은 보통이다" if m >= 70 else "시장 적용성은 더 확인해야 한다"
    action = "상용화는 적용처 검증과 이전 전략이 관건이다" if b >= 75 else "후속 실증과 수요처 검증이 필요하다"
    return f"{tech} {market}. {action}."


def ensure_conclusion(axis: str, score: int, reason: str) -> Dict[str, Any]:
    """점수 구간별 결론 문장 규칙: 마지막 문장이 허용 결론으로 끝나지 않으면 결론 문장을 붙인다."""
    band = grade(score)
    endings = CONCLUSIONS[band]
    text = reason.strip()
    if any(text.endswith(e) for e in endings):
        return {"text": text, "appended": False}
    return {"text": f"{text} 종합하면 {AXIS_LABEL[axis]}은 {endings[0]}".strip(), "appended": True}
