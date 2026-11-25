// 요약서 본문(상용화전망)의 기술완성도 서술과 TRL 판정을 일치시키는 결정론적 검증기.
// 요약서가 먼저 생성되고 TRL은 그 뒤 별도 호출로 판정되므로, 서술 단계와 TRL이 어긋나면
// TRL을 서술이 허용하는 범위로 보정한다.
// 단계는 문장 순서가 아니라 '현재 도달한 단계'로 정한다: 과거(거쳐·이후·완료)·현재(현재·단계에 있다·진행 중)로
// 서술된 단계 중 가장 높은 단계를 쓰고, 목표·예정·계획 같은 미래 단계와 경쟁 기술 서술은 세지 않는다.

export interface TrlBand { min: number; max: number; label: string }

const BANDS: Array<{ re: RegExp; band: TrlBand }> = [
  { re: /(개념\s*(?:증명|단계|수준)|원리\s*(?:수준|단계)|기초\s*연구\s*(?:수준|단계))/g, band: { min: 2, max: 3, label: "기초연구" } },
  // "실험실 개발 단계", "실험실 연구 수준", "실험실 내 검증"처럼 사이에 낱말이 하나 끼는 서술도 같은 단계로 본다
  { re: /(실험실(?:\s*(?:개발|연구|내|기반|차원))?\s*(?:수준|단계|규모|검증|에서)|랩\s*스케일|lab\s*scale|소규모\s*실험\s*(?:수준|단계)|실험\s*단계)/gi, band: { min: 3, max: 4, label: "실험실" } },
  { re: /(파일럿|시작품|시제품|프로토타입|실증\s*(?:단계|수준)|현장\s*(?:시험|실증|적용)\s*(?:단계|수준))/g, band: { min: 5, max: 6, label: "파일럿·실증" } },
  { re: /(양산\s*(?:준비|단계|가능(?!성)|체계)|즉시\s*(?:구현|적용|양산|생산)|기존\s*설비로\s*(?:바로|즉시|곧바로)?\s*(?:구현|생산|제조)|상용\s*(?:단계|수준)|시판\s*(?:중|되고))/g, band: { min: 7, max: 9, label: "양산준비" } },
];

type StageContext = "current" | "past" | "neutral" | "future" | "excluded";

// 앞쪽 문맥: 경쟁·대체 기술 서술이면 제외, 향후·단기·중기 등이면 미래 단계
const HEAD_EXCLUDED = /경쟁|대체\s*기술|기존\s*(?:기술|제품)|타사|해외\s*(?:업체|기업)|선진국/;
const HEAD_FUTURE = /향후|추후|앞으로|장기적|중기|단기|중장기|이후에는|\d+\s*년\s*(?:내|이내|후|까지)/;
const HEAD_CURRENT = /현재|이미|지금/;
// 뒤쪽 문맥(같은 절 안)
const TAIL_FUTURE = /목표|예정|계획|필요|요구|과제|앞두|전망|기대|향후|추후|못|않|미흡|미확보|부족|(?:확보|구축|진입|도달|전환|이행|추진|개발|달성|착수|진행)(?:할|하는\s*것|해야|하기|될)|(?:으로|로)의\s|에서는|시에는|경우/;
const TAIL_CURRENT = /현재|단계에\s*있|단계이다|단계다|수준이다|수준에\s*있|진행\s*중|진행되고|완료하고|완료했|완료하였|완료된|확보하고|확보했|확보한|보유|머물|도달했|진입했|중이다/;
const TAIL_PAST = /거쳐|거쳤|이후|마치고|마쳤|마친|검증되었|검증됐|검증을\s*완료|확인되었|확인됐|수행했|수행하였|입증|성공했|성공하였|완료|넘어|넘어선|벗어나|지나/;
const TRANSITION = /^(?:전환|진입|이행|넘어|나아|도약|발전|격상|올라|확대)/;
const CLAUSE_END = /(?:거쳐|거쳤고|이후|으며|하며|되며|이며|며|하고|되고|고|으나|지만|면서|는데|하여|해서)(?=\s|$)/;

/** 단계 표현 하나가 현재·과거(도달)·미래 중 무엇으로 서술됐는지 판정한다. */
function classifyStage(scope: string, start: number, end: number): StageContext {
  const headRaw = scope.slice(Math.max(0, start - 14), start);
  const head = headRaw.slice(Math.max(...[".", "。", ",", ";", "\n"].map((c) => headRaw.lastIndexOf(c))) + 1);
  let tail = scope.slice(end, end + 32);
  const stop = tail.search(/[.。,;\n]/);
  if (stop >= 0) tail = tail.slice(0, stop);
  const cl = CLAUSE_END.exec(tail);
  if (cl) tail = tail.slice(0, cl.index + cl[0].length);
  // "~ 단계로 / 수준으로"는 뒤에 전환·진입 같은 이동 동사가 오면 미래, 아니면 현재 단계 서술로 본다.
  const lo = tail.match(/^\s*(?:단계|수준|규모)?\s*(?:으로|로)\s+(\S+)/);
  if (lo && !/^(?:단계|수준|규모)?\s*(?:으로|로)의/.test(tail.trim())) {
    if (TRANSITION.test(lo[1])) return "future";
    tail = tail.slice(0, (lo.index ?? 0) + lo[0].length - lo[1].length);
    if (HEAD_EXCLUDED.test(head)) return "excluded";
    if (HEAD_FUTURE.test(head)) return "future";
    return "current";
  }
  if (HEAD_EXCLUDED.test(head)) return "excluded";
  if (/^\s*(?:을|를)?\s*(?:넘어|넘어선|벗어나|지나)/.test(tail)) return "past";
  if (HEAD_FUTURE.test(head) || TAIL_FUTURE.test(tail)) return "future";
  if (HEAD_CURRENT.test(head) || TAIL_CURRENT.test(tail)) return "current";
  if (TAIL_PAST.test(tail)) return "past";
  return "neutral";
}

/** 상용화전망 섹션의 위치(제목 포함). 섹션이 없으면 null. */
export function findCommercializationSection(summary: string): { start: number; bodyStart: number; end: number } | null {
  const h = /#{1,6}[ \t]*상용화\s*전망[^\n#]*?(?=\s|$)/.exec(summary) ?? /(?:^|\n)[ \t]*\**[ \t]*상용화\s*전망[ \t]*\**[ \t]*(?=\n)/.exec(summary);
  if (!h) return null;
  const start = h.index + (h[0].startsWith("\n") ? 1 : 0);
  const bodyStart = h.index + h[0].length;
  const rest = summary.slice(bodyStart);
  const next = rest.search(/(?:^|\s)#{1,6}\s/);
  return { start, bodyStart, end: next < 0 ? summary.length : bodyStart + next };
}

/** 상용화전망 섹션에서 현재 도달한 기술완성도 단계를 찾는다. 섹션이 없으면 판단하지 않는다(null). */
export function detectSummaryMaturity(summary: string): TrlBand | null {
  if (!summary) return null;
  const sec = findCommercializationSection(summary);
  if (!sec) return null;
  const scope = summary.slice(sec.bodyStart, sec.end);
  let marked = -1;  // 현재·과거로 서술된 단계 중 최고
  let neutral = -1; // 시제 표지가 없는 단계 중 최고
  BANDS.forEach(({ re }, rank) => {
    re.lastIndex = 0;
    for (const m of scope.matchAll(re)) {
      const ctx = classifyStage(scope, m.index!, m.index! + m[0].length);
      if (ctx === "current" || ctx === "past") marked = Math.max(marked, rank);
      else if (ctx === "neutral") neutral = Math.max(neutral, rank);
    }
  });
  const rank = marked >= 0 ? marked : neutral;
  return rank >= 0 ? BANDS[rank].band : null;
}

/** TRL이 서술 단계 범위를 벗어나면 범위 안으로 보정. changed=true면 근거문도 재작성해야 한다. */
export function reconcileTrl(trl: number, summary: string): { trl: number; changed: boolean; band: TrlBand | null } {
  const t = Math.max(1, Math.min(9, Math.round(Number(trl) || 5)));
  const band = detectSummaryMaturity(summary);
  if (!band) return { trl: t, changed: false, band };
  const fixed = Math.max(band.min, Math.min(band.max, t));
  return { trl: fixed, changed: fixed !== t, band };
}

const NEXT_STEP: Record<number, string> = {
  1: "핵심 원리에 대한 단편 실험 데이터가 확보되어야 다음 단계로 진입할 수 있다.",
  2: "단편 실험 데이터가 확보되어야 다음 단계로 진입할 수 있다.",
  3: "실험실 수준의 정량 데이터가 누적되어야 4단계로 진입할 수 있다.",
  4: "모사 환경의 통합 실시예가 보강되면 5단계로 진입 가능하다.",
  5: "파일럿·시작품 단계의 현장 적용 사례가 추가되면 6단계로 올라설 수 있다.",
  6: "실환경 운영 데이터가 누적되어야 상용화 단계인 7로 진입할 수 있다.",
  7: "기존 설비 기반의 안정적 양산·유통 근거가 확보되면 8단계로 인정 가능하다.",
  8: "동일 형태의 시판이 확인되면 9단계로 평가된다.",
  9: "동일 형태의 시판·유통이 이어지는 상용화 완료 단계로 본다.",
};

/**
 * TRL을 요약서 서술 단계에 맞춰 보정했을 때의 근거문. 고정 문구("실험실 수준의 수치 데이터가 확인돼")는
 * 원문에 없는 근거를 단정할 수 있으므로, 실제 판단 근거인 요약서의 서술 단계를 밝힌다. 점수·TRL 값은 바꾸지 않는다.
 */
export function describeTrlFromStage(trl: number, band: TrlBand): string {
  const t = Math.max(1, Math.min(9, Math.round(Number(trl) || 5)));
  const josa = t === 3 || t === 6 ? "으로" : "로";
  return `요약서 상용화전망이 기술완성도를 '${band.label}' 단계로 서술하고 있어 TRL ${t}${josa} 판단되며, ${NEXT_STEP[t]}`;
}

/**
 * 점수 산정용 요약 본문. 공백을 합치고 limit 글자로 줄이되, 상용화전망 섹션은 잘리지 않게 통째로 남긴다
 * (TRL 단계 판정과 사업성 근거가 이 섹션에 있으므로).
 */
export function buildScoringSummary(summary: string, limit = 3500): string {
  const collapse = (s: string) => s.replace(/\s+/g, " ").trim();
  const full = collapse(summary || "");
  if (full.length <= limit) return full;
  const sec = findCommercializationSection(summary);
  if (!sec) return full.slice(0, limit);
  const secText = collapse(summary.slice(sec.start, sec.end));
  const rest = collapse(`${summary.slice(0, sec.start)}\n${summary.slice(sec.end)}`);
  const budget = Math.max(0, limit - secText.length - 1);
  return collapse(`${rest.slice(0, budget)} ${secText}`);
}
