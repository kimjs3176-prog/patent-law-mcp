import { describe, it, expect } from "vitest";
import { describeTrlFromStage, reconcileTrl } from "../../supabase/functions/analyze-commercialization/trlConsistency";

// 실측 요약서(v19, 분자마커 특허) 상용화전망 발췌. 원문(초록·청구항)에는 실험 수치가 없다.
const MARKER = "## 상용화전망\n본 발명은 유효 마커 발굴 및 실험실 검증을 완료하고 표준화 프로토콜을 정립하였다. 단기적으로는 기술이전을 추진한다.\n";

describe("TRL 보정 근거문은 요약서의 서술 단계를 밝힌다", () => {
  it("보정된 TRL과 요약서 단계를 함께 쓰고, 원문에 없는 '수치 데이터 확인'을 단정하지 않는다", () => {
    const r = reconcileTrl(6, MARKER);
    expect(r).toMatchObject({ trl: 4, changed: true });
    const reason = describeTrlFromStage(r.trl, r.band!);
    expect(reason).toBe("요약서 상용화전망이 기술완성도를 '실험실' 단계로 서술하고 있어 TRL 4로 판단되며, 모사 환경의 통합 실시예가 보강되면 5단계로 진입 가능하다.");
    expect(reason).not.toMatch(/수치 데이터/);
  });

  it("TRL 숫자에 맞는 조사와 다음 단계 안내를 붙인다", () => {
    const band = { min: 5, max: 6, label: "파일럿·실증" };
    expect(describeTrlFromStage(6, band)).toContain("TRL 6으로 판단되며, 실환경 운영 데이터가");
    expect(describeTrlFromStage(5, band)).toContain("TRL 5로 판단되며, 파일럿·시작품 단계의");
    expect(describeTrlFromStage(3, { min: 3, max: 4, label: "실험실" })).toContain("TRL 3으로 판단되며");
    // 근거문 안의 TRL 숫자는 최종 TRL 하나뿐이어야 한다(analyze-commercialization의 재작성 조건).
    for (let t = 1; t <= 9; t++) {
      const nums = [...describeTrlFromStage(t, band).matchAll(/TRL\s*(\d)/g)].map((m) => Number(m[1]));
      expect(nums).toEqual([t]);
    }
  });
});
