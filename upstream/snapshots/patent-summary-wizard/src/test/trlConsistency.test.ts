import { describe, it, expect } from "vitest";
import { reconcileTrl } from "../../supabase/functions/analyze-commercialization/trlConsistency";

describe("TRL ↔ 상용화전망 정합성", () => {
  it("실험실 수준 서술이면 TRL 8을 4로 낮춘다", () => {
    const r = reconcileTrl(8, "## 상용화전망 본 기술은 현재 실험실 수준의 검증 단계로, 양산 공정은 미확보다.");
    expect(r.trl).toBe(4);
    expect(r.changed).toBe(true);
  });
  it("'실험실 개발 단계'처럼 낱말이 끼어도 실험실 단계로 보고 TRL 8을 4로 낮춘다", () => {
    const summary = "## 상용화 전망\n본 발명의 기술완성도는 특정 침지 온도 및 시간 조건에서 성분 증가를 확인한 실험실 개발 단계이며 대용량 가공 시 열전달 불균일 문제를 해결하는 스케일업 실증이 요구된다. 단기적으로는 기술이전이 유력하다.";
    const r = reconcileTrl(8, summary);
    expect(r.trl).toBe(4);
    expect(r.band?.label).toBe("실험실");
  });
  it("양산준비 서술이면 TRL 4를 7로 올린다", () => {
    expect(reconcileTrl(4, "## 상용화전망 기존 설비로 즉시 구현 가능한 양산 준비 단계다.").trl).toBe(7);
  });
  it("'실험실 수준을 넘어' 파일럿 서술이면 파일럿 범위로 본다", () => {
    expect(reconcileTrl(8, "## 상용화전망 실험실 수준을 넘어 파일럿 단계에서 검증되었다.").trl).toBe(6);
  });
  it("서술이 범위 안이면 그대로 둔다", () => {
    expect(reconcileTrl(5, "## 상용화전망 시작품 단계로 현장 검증이 필요하다.").changed).toBe(false);
  });
});
