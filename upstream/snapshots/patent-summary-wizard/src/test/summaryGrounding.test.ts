import { describe, it, expect } from "vitest";
import { sourceFigures, stripUnsupportedEffectFigures } from "../../supabase/functions/summarize-patent/summaryGrounding";
import { cacheApplicationEvidence, groundApplications, readApplicationEvidence } from "../../supabase/functions/summarize-patent/applicationGrounding";

const summaryOf = (body: string, section = "발명요약 및 특징") => `## ${section}\n${body}\n\n## 관련시장 동향\n국내 시장은 2023년 6,200억 원에서 연평균 6.8% 성장한다(AI 추정치).\n`;
const source = { abstract: "이 장치는 에너지를 절감하는 장치이다.", claims: ["1. 에너지 절감용 장치로서 제어부를 포함하는 장치."] };

describe("performance grounding", () => {
  it("removes invented 30% savings without asserting significant improvement", () => {
    const result = stripUnsupportedEffectFigures(summaryOf("에너지를 30% 절감한다."), source);
    expect(result).not.toContain("30%");
    expect(result).not.toContain("유의미");
    expect(result).toContain("추가 검증");
  });
  it("does not use ingredient concentration as evidence of 30% savings", () => {
    const result = stripUnsupportedEffectFigures(summaryOf("비용을 30% 절감한다."), { claims: ["설탕 30%를 포함하는 조성물."] });
    expect(result).not.toContain("30%");
  });
  it("preserves original metric and decimal value", () => {
    const input = summaryOf("에너지 소비량이 2.5% 감소한다.");
    expect(stripUnsupportedEffectFigures(input, { abstract: "에너지 소비량이 2.5% 감소한다." })).toBe(input);
  });
  it("preserves original composition and measured range", () => {
    const input = summaryOf("팥 99%와 설탕 1%로 구성한다. 회복률 73~100% 향상 개체를 선발한다.");
    expect(stripUnsupportedEffectFigures(input, { claims: ["팥 99%와 설탕 1% 조성. 회복률 73 내지 100% 향상 개체."] })).toBe(input);
  });
  it("checks technology-field assertions but preserves market numbers", () => {
    const result = stripUnsupportedEffectFigures(summaryOf("비용을 30% 절감한다.", "기술분야"), source);
    expect(result).not.toContain("30%");
    expect(result).toContain("6,200억 원");
    expect(result).toContain("6.8%");
  });
  it("removes unsupported duration and multiplier effects", () => {
    const result = stripUnsupportedEffectFigures(summaryOf("처리 시간이 3시간 단축된다. 수율이 2배 향상된다."), source);
    expect(result).not.toContain("3시간");
    expect(result).not.toContain("2배");
  });
  it("does not invent a high reliability when removing 99%", () => {
    const result = stripUnsupportedEffectFigures(summaryOf("99% 이상의 신뢰도로 판정한다."), source);
    expect(result).not.toContain("99%");
    expect(result).not.toContain("높은 신뢰도");
  });
  it("does not treat claim numbers as performance evidence", () => {
    expect(sourceFigures({ claims: ["30. 에너지 절감용 장치."] }).percent.size).toBe(0);
  });
  it("removes figures written after the performance verb", () => {
    expect(stripUnsupportedEffectFigures(summaryOf("에너지 절감률은 30%이다."), source)).not.toContain("30%");
  });
});

describe("application evidence", () => {
  const claims = "식품 발효용 조성물로서 유산균을 포함하는 조성물이다.";
  const description = "상기 조성물은 가축 사료 제조에 사용할 수 있다.";
  it("marks a directly stated claim use true", () => {
    const result = groundApplications(`[[용도|청구항|식품 발효|${claims}]] 식품에 쓴다.`, { claims: [claims], description });
    expect(result.applications[0]).toEqual({ label: "식품 발효", claimed_in_claims: true, source: "claims", evidence: claims });
  });
  it("downgrades a description-only use despite model claim label", () => {
    const result = groundApplications(`[[용도|청구항|가축 사료|${description}]] 사료에 쓴다.`, { claims: [claims], description });
    expect(result.applications[0]?.claimed_in_claims).toBe(false);
    expect(result.applications[0]?.source).toBe("description");
  });
  it("rejects fabricated excerpts and unrelated use labels", () => {
    expect(groundApplications(`[[용도|청구항|치료|${claims}]]`, { claims: [claims] }).applications).toHaveLength(0);
    expect(groundApplications("[[용도|청구항|치료|암 치료에 사용하는 새로운 조성물이다.]]", { claims: [claims] }).applications).toHaveLength(0);
  });
  it("keeps claim booleans across cached views and removes storage metadata from prose", () => {
    const grounded = groundApplications(`[[용도|청구항|식품 발효|${claims}]]`, { claims: [claims] });
    const cached = readApplicationEvidence(cacheApplicationEvidence(grounded.content, grounded.applications), { claims: [claims] });
    expect(cached.content).toBe(grounded.content);
    expect(cached.applications[0]?.claimed_in_claims).toBe(true);
    expect(readApplicationEvidence(cacheApplicationEvidence(grounded.content, grounded.applications), { claims: [description] }).applications).toHaveLength(0);
  });
});