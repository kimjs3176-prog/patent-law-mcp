import type { GroundingSource } from "./summaryGrounding.ts";

export interface GroundedApplication {
  label: string;
  claimed_in_claims: boolean;
  source: "claims" | "description";
  evidence: string;
}

export const APPLICATION_GROUNDING_INSTRUCTION = `
[활용 용도 근거 구분 — 최우선]
농산업활용 가능성의 각 용도 문단 첫머리에 [[용도|청구항|용도명|원문 연속 발췌]] 또는 [[용도|명세서|용도명|원문 연속 발췌]]를 붙인다.
용도명은 발췌에 직접 등장하는 짧은 명사구로 쓴다. 발췌는 해당 청구항 또는 설명·초록의 연속된 원문 15~200자이며 요약하거나 재작성하지 않는다. |, 줄바꿈, ]]는 발췌에 넣지 않는다.
청구항에 용도가 직접 기재된 경우만 청구항으로 분류한다. 성분·균주·장치가 청구되었다는 이유만으로 명세서의 모든 용도가 청구된 것으로 간주하지 않는다.
설명·초록에만 등장한 용도는 명세서로 분류하고 청구항 권리범위와 동일시하지 않는다. 근거 없는 인접 분야 확장은 쓰지 않는다.
청구항 명시는 법적 권리범위 확정이나 등록·실시 보장을 의미하지 않는다. 해당 용도의 근거가 없으면 용도를 지어내지 말고 원문 확인이 필요하다고 쓴다.`;

const normalize = (s: string) => s.replace(/\s+/g, " ").trim();

/** Model-proposed source labels are accepted only with a verbatim source excerpt. */
export function groundApplications(summary: string, source: GroundingSource | null | undefined) {
  const applications: GroundedApplication[] = [];
  const claims = normalize(Array.isArray(source?.claims) ? source.claims.join("\n") : source?.claims ?? "");
  const description = normalize([source?.abstract, source?.description].filter(Boolean).join("\n"));
  const content = summary.replace(/\[\[용도\|([^|\]\n]*)\|([^|\]\n]*)\|([^\]\n]*)\]\]/g, (_full, kind: string, rawLabel: string, rawEvidence: string) => {
    const label = normalize(rawLabel);
    const evidence = normalize(rawEvidence);
    const valid = label.length >= 2 && label.length <= 60 && evidence.length >= 15 && evidence.length <= 200 && evidence.includes(label);
    const inClaims = valid && kind === "청구항" && /(?:용|제조|생산|처리|방제|치료|예방|검출|진단|재배|발효|추출)/.test(evidence) && claims.includes(evidence);
    const inDescription = valid && description.includes(evidence);
    if (!inClaims && !inDescription) return "**용도 근거 미확인** — 아래 활용 설명은 원문 대조가 필요하다. ";
    applications.push({ label, claimed_in_claims: inClaims, source: inClaims ? "claims" : "description", evidence });
    return `**${inClaims ? "청구항 명시 용도" : "명세서 일반 용도"}: ${label}**. `;
  });
  // Never expose malformed machine markers as a confirmed claim.
  return { content: content.replace(/\[\[용도[^\n]*(?:\]\]|$)/g, "용도 근거 미확인. "), applications };
}

/** Store source proposals beside the prose, never in a new public table. Revalidate on read. */
export function cacheApplicationEvidence(content: string, applications: GroundedApplication[]): string {
  return content + `\n<!--application-evidence:${encodeURIComponent(JSON.stringify(applications))}-->`;
}

export function readApplicationEvidence(content: string, source: GroundingSource | null | undefined) {
  const match = content.match(/\n<!--application-evidence:([^\n]*?)-->\s*$/);
  const prose = content.replace(/\n<!--application-evidence:[^\n]*?-->\s*$/, "");
  if (!match) return { content: prose, applications: [] as GroundedApplication[] };
  try {
    const records: unknown = JSON.parse(decodeURIComponent(match[1]));
    if (!Array.isArray(records)) return { content: prose, applications: [] as GroundedApplication[] };
    const proposals = records.filter((r) => r && typeof r.label === "string" && typeof r.evidence === "string" && typeof r.claimed_in_claims === "boolean")
      .map((r) => `[[용도|${r.claimed_in_claims ? "청구항" : "명세서"}|${r.label}|${r.evidence}]]`).join("\n");
    return { content: prose, applications: groundApplications(proposals, source).applications };
  } catch { return { content: prose, applications: [] as GroundedApplication[] }; }
}