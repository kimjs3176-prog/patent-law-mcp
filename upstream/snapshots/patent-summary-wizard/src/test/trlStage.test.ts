import { describe, it, expect } from "vitest";
import { buildScoringSummary, detectSummaryMaturity, reconcileTrl } from "../../supabase/functions/analyze-commercialization/trlConsistency";

const sec = (body: string) => `## 기술분야\n농업용 미생물 제제 기술이다.\n\n## 상용화전망\n${body}\n`;

describe("TRL 단계 판정은 문장 순서와 무관하게 현재 도달 단계로 정한다", () => {
  it("같은 사실을 순서만 바꿔도 같은 TRL", () => {
    const a = sec("본 기술은 실험실 검증과 파일럿 실증을 거쳐 양산 준비 단계에 있다.");
    const b = sec("본 기술은 현재 양산 준비 단계에 있으며, 실험실 검증과 파일럿 실증을 거쳤다.");
    expect(detectSummaryMaturity(a)?.label).toBe("양산준비");
    expect(detectSummaryMaturity(b)?.label).toBe("양산준비");
    expect(reconcileTrl(4, a).trl).toBe(reconcileTrl(4, b).trl);
    expect(reconcileTrl(4, a).trl).toBe(7);
  });

  it("목표·예정·계획으로 서술된 단계는 도달 단계로 세지 않는다", () => {
    const s = sec("현재 실험실 수준의 검증을 완료했으며, 2027년 파일럿 실증을 목표로 하고 양산 준비는 2029년 예정이다.");
    expect(detectSummaryMaturity(s)?.label).toBe("실험실");
    expect(reconcileTrl(7, s).trl).toBe(4);
  });

  it("'~단계로 전환할 계획'은 미래, '~단계로 …가 필요하다'는 현재 단계", () => {
    expect(detectSummaryMaturity(sec("파일럿 실증 이후 양산 준비 단계로 전환할 계획이다."))?.label).toBe("파일럿·실증");
    expect(detectSummaryMaturity(sec("시작품 단계로 현장 검증이 필요하다."))?.label).toBe("파일럿·실증");
  });

  it("향후·단기·중기 경로와 경쟁 기술 서술은 현재 단계가 아니다", () => {
    expect(detectSummaryMaturity(sec("단기(1~2년) 내 파일럿 실증을 거쳐 중기(3~5년)에는 양산 체계를 구축할 계획이다."))).toBeNull();
    expect(detectSummaryMaturity(sec("현재 실험실 단계이며, 경쟁 기술은 이미 상용 단계에 있다."))?.label).toBe("실험실");
  });

  it("상용화전망 섹션이 없으면 다른 섹션을 보지 않고 판정하지 않는다", () => {
    const noSection = "## 기술분야\n본 기술은 양산 준비 단계에 있다.\n\n## 발명요약 및 특징\n실험실 수준의 결과다.\n";
    expect(detectSummaryMaturity(noSection)).toBeNull();
    expect(reconcileTrl(3, noSection)).toEqual({ trl: 3, changed: false, band: null });
  });
});

describe("점수 산정용 요약 자르기", () => {
  it("짧으면 공백만 정리한다", () => {
    expect(buildScoringSummary("## A\n가  나\n\n## 상용화전망\n다")).toBe("## A 가 나 ## 상용화전망 다");
  });
  it("길어도 상용화전망 섹션은 끝까지 남긴다", () => {
    const filler = "가".repeat(5000);
    const tail = "본 기술은 실험실 검증과 파일럿 실증을 거쳐 양산 준비 단계에 있다.";
    const s = `## 기술분야\n${filler}\n\n## 상용화전망\n${tail}\n`;
    const out = buildScoringSummary(s, 3500);
    expect(out.length).toBeLessThanOrEqual(3500);
    expect(out.endsWith(`## 상용화전망 ${tail}`)).toBe(true);
    expect(detectSummaryMaturity(out)?.label).toBe("양산준비");
  });
  it("상용화전망 뒤에 다른 섹션이 있어도 그 섹션 전체를 유지한다", () => {
    const s = `## 상용화전망\n현재 파일럿 단계다.\n\n## 기타\n${"나".repeat(5000)}`;
    const out = buildScoringSummary(s, 3500);
    expect(out).toContain("## 상용화전망 현재 파일럿 단계다.");
    expect(out.length).toBeLessThanOrEqual(3500);
  });
});
