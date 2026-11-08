// 원문에 없는 '효과 수치'를 요약서에서 걷어내는 결정론적 보정기.
// 원문(초록·청구항·설명)에 없는 "30% 이상 감소", "약제 낭비를 15% 이상 방지", "손실률을 5% 미만으로 억제"처럼
// AI가 지어낸 정량 효과는 농가가 사실로 읽기 쉬우므로, 수치만 빼고 같은 문장을 정성 표현으로 남긴다.
// 원문에 있는 수치(청구항의 배합비·회복률 등)와 시장 섹션(별도 신뢰 규칙 적용)은 건드리지 않는다.

export interface GroundingSource {
  title?: string;
  abstract?: string;
  claims?: string[] | string;
  description?: string;
}

/** 효과 수치를 검사하는 섹션(발명요약·농산업활용·상용화전망). 기술분야·관련시장 동향은 제외한다. */
const EFFECT_SECTION_RE = /(^##[ \t]*(?:기술\s*분야|발명\s*요약|농산업\s*활용|상용화\s*전망)[^\n]*\n)([\s\S]*?)(?=^##\s|$(?![\s\S]))/gm;

const NUM = String.raw`\d+(?:[.,]\d+)*`;
const RANGE = String.raw`${NUM}(?:\s*[~∼～〜\-–]\s*${NUM})?`;
// 효과를 나타내는 서술어(어간). 수치 바로 뒤에 와야 '효과 수치'로 본다.
const EFFECT_VERB = String.raw`(?:절감|감소|감축|저감|향상|증가|증대|개선|단축|방지|억제|줄|높|낮|늘|상승|하락|제고|축소|완화|경감)`;
const QUALIFIER = String.raw`(?:이상|이하|가량|내외|정도|수준|까지|가까이|남짓)`;

// "기존 대비 약 70% 이상 절감", "이병률 30% 이상 감소", "약제 낭비를 15% 이상 방지", "약 2.5배 향상"
const EFFECT_FIGURE_RE = new RegExp(
  String.raw`(?:(?:기존|종전|관행|일반)\s*(?:[가-힣]{1,6}\s*)?대비\s*)?(?:약\s*|최대\s*|평균\s*)?(${RANGE})\s*(%|배)\s*${QUALIFIER}?\s*(?:의\s*)?(?=\**\s*${EFFECT_VERB})`,
  "g",
);
// "실패율을 10% 미만으로 억제" → "실패율을 낮은 수준으로 억제"
const CEILING_RE = new RegExp(String.raw`(?:약\s*)?(${RANGE})\s*%\s*(?:미만|이하|이내)(\**)\s*(으로|로)(?=\s)`, "g");
// "99% 이상의 신뢰도로" → "높은 신뢰도로"
const FLOOR_NOUN_RE = new RegExp(
  String.raw`(?:약\s*)?(${RANGE})\s*%\s*(?:이상|대)의\s*(?=\**\s*(?:신뢰도|정확도|정확성|판별률|판별\s*정확도|재현성|검출률|회수율|생존율|순도|효율))`,
  "g",
);

function sourceText(src: GroundingSource | null | undefined): string {
  if (!src) return "";
  const claims = Array.isArray(src.claims) ? src.claims.join("\n") : String(src.claims ?? "");
  return [src.title, src.abstract, claims, src.description].filter(Boolean).join("\n");
}

const normNum = (n: string) => n.replace(/,/g, "").replace(/^0+(?=\d)/, "");

export interface SourceFigures { percent: Set<string>; times: Set<string> }

/**
 * 원문에서 단위와 함께 쓰인 수치를 모은다(%·배). "73 내지 100%"처럼 범위로 쓰인 하한도 포함한다.
 * 단위 없이 나온 숫자(서열번호·청구항 번호 등)는 효과 수치의 근거로 보지 않는다.
 */
export function sourceFigures(src: GroundingSource | null | undefined): SourceFigures {
  const text = sourceText(src);
  const collect = (unit: string) => {
    const out = new Set<string>();
    const re = new RegExp(String.raw`(${NUM})(?:\s*(?:[~∼～〜\-–]|내지|에서|부터)\s*(${NUM}))?\s*(?:${unit})`, "g");
    for (const m of text.matchAll(re)) {
      out.add(normNum(m[1]));
      if (m[2]) out.add(normNum(m[2]));
    }
    return out;
  };
  return { percent: collect("%|퍼센트|중량%|wt%"), times: collect("배") };
}

function rangeSupported(range: string, unit: string, figs: SourceFigures): boolean {
  const set = unit === "배" ? figs.times : figs.percent;
  return range.split(/\s*[~∼～〜\-–]\s*/).every((n) => set.has(normNum(n)));
}

// Lexical metric stems only; never rewrite Korean words or particles in the output.
const metricTerms = (text: string): string[] => text.match(/(?:[가-힣]{0,8}(?:비용|수율|효율|정확도|신뢰도|회복률|회수율|생존율|순도|손실률|실패율|이병률|살포량|시간|에너지|소비량|노동력|감염|항균활성))/g) ?? [];
const sentences = (text: string): string[] => text.match(/[\s\S]+?(?:[.!?](?=\s|$)|\n|$)/g) ?? [];

/** A matching number alone (e.g. ingredient concentration) is not evidence of performance. */
function contextualSupport(range: string, unit: string, sentence: string, src: GroundingSource): boolean {
  const terms = metricTerms(sentence);
  return sentences(sourceText(src)).some((excerpt) => {
    if (!rangeSupported(range, unit, sourceFigures({ description: excerpt }))) return false;
    if (!new RegExp(EFFECT_VERB).test(excerpt) && !/(?:회복률|회수율|정확도|신뢰도|효율|수율|생존율|순도)/.test(excerpt)) return false;
    return metricTerms(excerpt).some((word) => terms.includes(word));
  });
}

const OTHER_EFFECT_FIGURE_RE = new RegExp(String.raw`(?:약\s*|최대\s*|평균\s*)?(${RANGE})\s*(시간|분|초|일|개월|년|회|원|kWh|킬로와트시)\s*${QUALIFIER}?\s*(?:의\s*)?(?=\**\s*${EFFECT_VERB})`, "g");
const REVERSE_EFFECT_RE = new RegExp(String.raw`(${EFFECT_VERB}[가-힣]*\s*(?:효과|율|률)?\s*(?:은|는|이|가|:)?\s*)(?:약\s*)?(${RANGE})\s*(%|배)`, "g");

function cleanup(body: string): string {
  return body
    .replace(/\*\*\s*\*\*/g, "")
    // 수치를 뺀 문장에 남는 "정량적 개선 효과" 같은 표현도 정성 표현으로 맞춘다.
    .replace(/정량적\s*(?=(?:개선\s*)?(?:효과|가치|성과))/g, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+([,.])/g, "$1");
}

/**
 * 발명요약·농산업활용·상용화전망에서 원문에 없는 효과 수치(%, 배)를 빼고 정성 표현으로 바꾼다.
 * 원문을 알 수 없으면(빈 원문) 판단하지 않고 그대로 둔다.
 */
export function stripUnsupportedEffectFigures(summary: string, src: GroundingSource | null | undefined): string {
  if (!summary) return summary;
  if (!sourceText(src).trim()) return summary;
  return summary.replace(EFFECT_SECTION_RE, (_m, heading: string, body: string) => {
    // Split only at sentence endings, not decimal points. Keep every original separator.
    const outBody = sentences(body).map((sentence: string) => {
    let changed = false;
    let out = sentence.replace(EFFECT_FIGURE_RE, (full: string, range: string, unit: string) => {
      if (src && contextualSupport(range, unit, sentence, src)) return full;
      changed = true;
      return "";
    });
    out = out.replace(CEILING_RE, (full: string, range: string, bold: string, josa: string) => {
      if (src && contextualSupport(range, "%", sentence, src)) return full;
      changed = true;
      return `확인되지 않은 수준${bold}${josa === "로" ? "으로" : josa}`;
    });
    out = out.replace(FLOOR_NOUN_RE, (full: string, range: string) => {
      if (src && contextualSupport(range, "%", sentence, src)) return full;
      changed = true;
      return "검증이 필요한 ";
    });
    out = out.replace(OTHER_EFFECT_FIGURE_RE, (full: string, range: string, unit: string) => {
      const supported = sentences(sourceText(src)).some((excerpt) => {
        const figure = new RegExp(`${range.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*${unit}`);
        return figure.test(excerpt) && new RegExp(EFFECT_VERB).test(excerpt) && metricTerms(excerpt).some((term) => metricTerms(sentence).includes(term));
      });
      if (supported) return full;
      changed = true;
      return "";
    });
    out = out.replace(REVERSE_EFFECT_RE, (full: string, prefix: string, range: string, unit: string) => {
      if (src && contextualSupport(range, unit, sentence, src)) return full;
      changed = true;
      return prefix + "추가 검증 필요";
    });
    // With no matching metric in the source, even a qualitative improvement is unverified.
    if (changed) {
      // Do not turn an invented percentage into an equally invented 'significant' improvement.
      const labels = sentence.match(/^\s*\*\*(?:청구항 명시 용도|명세서 일반 용도):[^*]+\*\*\.\s*/)?.[0] ?? "";
      const metric = metricTerms(sentence)[0];
      return `${sentence.startsWith(" ") ? " " : ""}${labels}${metric ? `${metric} 관련 효과는` : "해당 효과는"} 원문에 정량 근거가 없어 추가 검증이 필요하다.${sentence.endsWith("\n") ? "\n" : " "}`;
    }
    return changed ? cleanup(out) : sentence;
    }).join("");
    return heading + outBody;
  });
}
