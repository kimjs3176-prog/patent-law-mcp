"""국가법령정보센터 원문 정기 대조

정책 YAML의 기준값이 기대는 법령·고시 조문(policies/legal_sources.yaml)을 국가법령정보센터의 현재 시행 원문과 비교합니다.

- 기준선: policies/legal_baseline.json (마지막으로 사람이 대조·확인한 버전과 조문 본문)
- check_sources(): 버전 변경, 감시 조문 본문 변경·삭제, 기준값 문구(phrases) 누락을 찾아 보고
- update_baseline(): 변경을 검토·반영한 뒤 기준선을 현재 원문으로 갱신

인증키(LAW_OC) 없이 공개 웹 화면을 읽습니다. 화면 구조가 바뀌면 오류로 알립니다 (조용히 '변경 없음'으로 처리하지 않음).
"""

import difflib
import hashlib
import json
import re
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
from bs4 import BeautifulSoup

from patent_law_mcp import cache, net

POLICY_DIR = Path(__file__).parent / "policies"
SOURCES_FILE = POLICY_DIR / "legal_sources.yaml"
BASELINE_FILE = POLICY_DIR / "legal_baseline.json"
SITE = "https://www.law.go.kr"
_HEAD = re.compile(r"(?m)^\s*(제\s*\d+\s*조(?:\s*의\s*\d+)?)\s*\(([^)\n]{1,60})\)")
_ADDENDA = re.compile(r"(?m)^\s*부\s*칙")
MAX_DIFF_LINES = 40


class LawSourceError(RuntimeError):
    """원문을 받지 못했거나 화면 구조가 예상과 다를 때"""


# ---------------------------------------------------------------- 원문 수집
def _get(url: str) -> str:
    r = net.http_get(url, timeout=40, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _post(url: str, data: Dict[str, str]) -> str:
    r = net.http_post(url, data=data, timeout=60)
    r.raise_for_status()
    return r.text


def _page_url(source: Dict[str, Any]) -> str:
    kind = "법령" if source["kind"] == "law" else "행정규칙"
    return f"{SITE}/{kind}/{urllib.parse.quote(source['name'].replace(' ', ''))}"


def resolve_version(source: Dict[str, Any], get: Callable[[str], str] = _get) -> Dict[str, str]:
    """현재 시행 중인 버전의 식별자(법령 lsiSeq·efYd, 행정규칙 admRulSeq)를 찾습니다."""
    html = get(_page_url(source))
    if source["kind"] == "law":
        seq = re.search(r"lsiSeq\s*[:=]\s*'?(\d+)", html)
        ef = re.search(r"efYd\s*[:=]\s*'?(\d{8})", html)
        if not (seq and ef):
            raise LawSourceError(f"{source['name']}: 법령 화면에서 lsiSeq·efYd를 찾지 못했습니다 (화면 구조 변경 가능).")
        return {"seq": seq.group(1), "effective_date": ef.group(1)}
    seq = re.search(r'id="admRulSeq"\s+value="(\d+)"', html) or re.search(r'admRulSeq\s*:\s*"(\d+)"', html)
    if not seq:
        raise LawSourceError(f"{source['name']}: 행정규칙 화면에서 admRulSeq를 찾지 못했습니다 (화면 구조 변경 가능).")
    return {"seq": seq.group(1), "effective_date": ""}


def _to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    return soup.get_text("\n")


def split_articles(text: str) -> Dict[str, str]:
    """본문 텍스트를 '제N조'·'제N조의M' 단위로 나눕니다 (부칙 이후는 제외, 공백 정규화)."""
    cut = _ADDENDA.search(text)
    if cut:
        text = text[: cut.start()]
    marks = list(_HEAD.finditer(text))
    out: Dict[str, str] = {}
    for i, m in enumerate(marks):
        key = re.sub(r"\s+", "", m.group(1))
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.setdefault(key, re.sub(r"\s+", " ", text[m.start():end]).strip())
    return out


def fetch_articles(source: Dict[str, Any], version: Dict[str, str], post: Callable[[str, Dict[str, str]], str] = _post) -> Dict[str, str]:
    if source["kind"] == "law":
        html = post(f"{SITE}/LSW/lsInfoR.do", {
            "lsiSeq": version["seq"], "efYd": version["effective_date"], "chrClsCd": "010202", "ancYnChk": "0",
        })
    else:
        html = post(f"{SITE}/LSW/admRulLsInfoR.do", {"admRulSeq": version["seq"]})
    articles = split_articles(_to_text(html))
    if not articles:
        raise LawSourceError(f"{source['name']}: 본문에서 조문을 찾지 못했습니다 (화면 구조 변경 가능).")
    return articles


def fetch_current(source: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    version = resolve_version(source)
    return version, fetch_articles(source, version)


# ---------------------------------------------------------------- 기준선 비교
def load_sources(path: Path = SOURCES_FILE) -> List[Dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list) or not sources:
        raise LawSourceError(f"{path.name}에 sources 목록이 없습니다.")
    return sources


def load_baseline(path: Path = BASELINE_FILE) -> Dict[str, Any]:
    if not path.exists():
        return {"verified_on": None, "sources": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _diff(old: str, new: str) -> List[str]:
    split = lambda s: re.split(r"(?<=[.。)])\s+|\s(?=[①-⑳])|\s(?=\d+\.\s)", s)  # noqa: E731
    lines = list(difflib.unified_diff(split(old), split(new), "기준선", "현재", lineterm="", n=0))
    return lines[:MAX_DIFF_LINES] + (["… (생략)"] if len(lines) > MAX_DIFF_LINES else [])


def compare_source(
    source: Dict[str, Any], base: Optional[Dict[str, Any]], version: Dict[str, str], articles: Dict[str, str]
) -> Dict[str, Any]:
    """한 법령의 현재 원문을 기준선과 비교한 결과."""
    short = source.get("short", source["name"])
    findings: List[Dict[str, Any]] = []
    base = base or {}
    base_articles = base.get("articles", {})
    version_changed = bool(base) and base.get("seq") != version["seq"]

    for art, phrases in (source.get("articles") or {}).items():
        current = articles.get(art)
        label = f"{short} {art}"
        if current is None:
            findings.append({"article": label, "type": "조문 없음", "detail": "현재 원문에서 이 조문을 찾지 못했습니다 (삭제·이동 가능)."})
            continue
        old = base_articles.get(art)
        if old is None:
            findings.append({"article": label, "type": "기준선 없음", "detail": "기준선에 이 조문이 없습니다. 원문을 확인한 뒤 --update로 기준선에 넣으십시오."})
        elif old["sha256"] != _sha(current):
            findings.append({"article": label, "type": "본문 변경", "detail": "기준선과 본문이 다릅니다.", "diff": _diff(old["text"], current)})
        for p in phrases or []:
            if re.sub(r"\s+", "", p["phrase"]) not in re.sub(r"\s+", "", current):  # 링크 등으로 끼어든 공백 무시
                findings.append({
                    "article": label, "type": "기준값 문구 없음",
                    "detail": f"'{p['phrase']}' 문구가 원문에 없습니다. 영향 받는 값: {p['policy']}",
                })

    status = "변경 있음" if findings or version_changed else "변경 없음"
    if not base:
        status = "기준선 없음"
    return {
        "id": source["id"],
        "name": source["name"],
        "status": status,
        "baseline_version": {k: base.get(k) for k in ("seq", "effective_date")} if base else None,
        "current_version": version,
        "version_changed": version_changed,
        "findings": findings,
        "url": _page_url(source),
    }


def check_sources(
    ids: Optional[List[str]] = None,
    fetch: Callable[[Dict[str, Any]], Tuple[Dict[str, str], Dict[str, str]]] = fetch_current,
) -> Dict[str, Any]:
    sources = [s for s in load_sources() if not ids or s["id"] in ids]
    baseline = load_baseline()
    results, errors = [], []
    for s in sources:
        try:
            version, articles = fetch(s)
        except Exception as e:  # noqa: BLE001 — 법령 하나 실패가 전체 점검을 막지 않도록
            errors.append({"id": s["id"], "name": s["name"], "error": f"{type(e).__name__}: {e}"[:300]})
            continue
        results.append(compare_source(s, baseline["sources"].get(s["id"]), version, articles))
    changed = [r for r in results if r["status"] != "변경 없음"]
    return {
        "checked_on": date.today().isoformat(),
        "baseline_verified_on": baseline.get("verified_on"),
        "summary": "점검 오류 있음" if errors else ("변경 있음 — 원문 검토 필요" if changed else "변경 없음"),
        "changed": changed,
        "unchanged": [r["name"] for r in results if r["status"] == "변경 없음"],
        "errors": errors,
    }


def update_baseline(
    ids: Optional[List[str]] = None,
    fetch: Callable[[Dict[str, Any]], Tuple[Dict[str, str], Dict[str, str]]] = fetch_current,
    path: Path = BASELINE_FILE,
) -> Dict[str, Any]:
    """현재 원문으로 기준선을 갱신합니다. 원문 검토와 정책 YAML 반영을 마친 뒤에만 실행하십시오."""
    baseline = load_baseline(path)
    updated = []
    for s in load_sources():
        if ids and s["id"] not in ids:
            continue
        version, articles = fetch(s)
        missing = [a for a in (s.get("articles") or {}) if a not in articles]
        if missing:
            raise LawSourceError(f"{s['name']}: 감시 조문 {', '.join(missing)}이(가) 원문에 없습니다. legal_sources.yaml을 먼저 고치십시오.")
        baseline["sources"][s["id"]] = {
            "name": s["name"],
            **version,
            "articles": {a: {"sha256": _sha(articles[a]), "text": articles[a]} for a in (s.get("articles") or {})},
        }
        updated.append(s["name"])
    baseline["verified_on"] = date.today().isoformat()
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"updated": updated, "verified_on": baseline["verified_on"]}


def render_report(result: Dict[str, Any]) -> str:
    """점검 결과를 이슈 본문용 마크다운으로."""
    out = [
        "## 국가법령정보 원문 점검 결과",
        "",
        f"- 점검일: {result['checked_on']} · 기준선 대조일: {result['baseline_verified_on']}",
        f"- 결과: **{result['summary']}**",
        "",
    ]
    for r in result["changed"]:
        cur, old = r["current_version"], r["baseline_version"] or {}
        out.append(f"### [{r['name']}]({r['url']}) — {r['status']}")
        if r["version_changed"]:
            out.append(f"- 버전 변경: {old.get('seq')} ({old.get('effective_date') or '-'}) → {cur['seq']} ({cur.get('effective_date') or '-'})")
        if not r["findings"]:
            out.append("- 감시 조문 본문은 그대로입니다 (다른 조문 개정 또는 타법개정). 확인 후 기준선만 갱신하면 됩니다.")
        for f in r["findings"]:
            out.append(f"- **{f['article']}** · {f['type']} — {f['detail']}")
            if f.get("diff"):
                out += ["  ```diff", *[f"  {line}" for line in f["diff"]], "  ```"]
        out.append("")
    if result["errors"]:
        out.append("### 점검 오류")
        out += [f"- {e['name']}: {e['error']}" for e in result["errors"]]
        out.append("")
    out += [
        "### 반영 절차",
        "1. 위 링크의 원문을 읽고, 바뀐 조문이 `policies/*.yaml` 기준값·근거 조항·도구 문구에 영향을 주는지 확인합니다.",
        "2. 값이 바뀌었으면 정책 YAML과 테스트를 고칩니다 (문구에 적힌 '영향 받는 값'부터).",
        "3. `uv run python scripts/check_law_sources.py --update`로 기준선을 갱신하고 PR을 엽니다.",
    ]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- MCP 도구
def check_legal_source_updates(refresh: bool = False) -> Dict[str, Any]:
    """정책 기준값의 근거 법령·고시가 마지막 원문 대조 이후 바뀌었는지 국가법령정보센터 현재 원문으로 확인합니다.

    버전(공포·시행) 변경, 감시 조문의 본문 변경·삭제, 기준값 문구(예: '300만원', '3퍼센트') 누락을 보고합니다.
    결과는 24시간 캐시합니다. 인증키가 필요 없습니다.

    Args:
        refresh: True면 캐시를 무시하고 다시 확인
    """
    key = load_baseline().get("verified_on") or "none"
    if not refresh:
        hit = cache.get("legal_sources", key, ttl_hours=24)
        if hit:
            return hit
    result = check_sources()
    for r in result["changed"]:  # MCP 응답은 diff를 짧게
        for f in r["findings"]:
            if f.get("diff"):
                f["diff"] = f["diff"][:12]
    result["how_to_use"] = (
        "summary가 '변경 없음'이면 도구 결과의 기준값을 그대로 써도 됩니다. '변경 있음'이면 해당 법령의 changed 항목과 "
        "링크된 원문을 먼저 확인하고, 영향 받는 값이 들어간 답변에는 그 사실을 함께 알리십시오."
    )
    if not result["errors"]:
        cache.put("legal_sources", key, result)
    return result


def baseline_status() -> Dict[str, Any]:
    """도구 출력에 붙이는 원문 대조 기준일."""
    base = load_baseline()
    return {"verified_on": base.get("verified_on"), "how_to_check": "check_legal_source_updates 도구로 이후 개정 여부 확인"}
