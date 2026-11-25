/** User-provided terminology; presentation only, never changes estimated TRL scores. */
export const TRL_REFERENCE_LEVELS = [
  { level: 1, label: "기초이론 정립", description: "기초 이론·실험", example: "현상·원리 발견" },
  { level: 2, label: "기술개념 정립", description: "실용 목적의 아이디어·특허 등 개념 정립", example: "용도 착안, 출원 직전" },
  { level: 3, label: "개념 실증", description: "연구실 규모의 기본성능 검증", example: "추출물 활성 1차 확인" },
  { level: 4, label: "실험실 검증", description: "연구실 규모의 핵심성능 평가", example: "세포 수준 효능, 마커·프라이머 실험실 검증" },
  { level: 5, label: "시제품 성능 평가", description: "확정된 시작품 제작 및 성능 평가", example: "동물모델 효능, 최적 공정조건 확정, 표준 PCR 조건 확립" },
  { level: 6, label: "파일럿 실증", description: "파일럿 규모 시작품 제작 및 성능 평가", example: "파일럿 추출·시제품 현장 테스트, 장치 실증" },
  { level: 7, label: "신뢰성 검증", description: "신뢰성 평가 및 수요기업 평가", example: "임상(반려견 등)·실사용 환경 검증, 수요처 평가" },
  { level: 8, label: "인증·표준화", description: "시제품 인증 및 표준화", example: "KC 인증, 기능성 원료 인정, 표준 검사법 등재" },
  { level: 9, label: "사업화", description: "사업화", example: "양산·판매 중" },
];

const LEGACY_LEVELS = [
  ["기초연구", "기본 원리 관찰 및 보고"],
  ["기술개념", "기술 개념 및 응용 정립"],
  ["개념검증", "핵심 기능의 분석적/실험적 증명"],
  ["실험실검증", "실험실 환경에서 기술 검증"],
  ["유사환경검증", "유사 환경에서 기술 검증"],
  ["시제품개발", "시제품의 유사 환경 시연"],
  ["운영환경시연", "실제 운영 환경에서 시연"],
  ["시스템완성", "시스템 완성 및 검증"],
  ["상용화", "실제 운영 환경에서 성공적 검증"],
];

/** Upgrade old defaults, retaining intentionally customized labels/descriptions. */
export function resolveTrlLevels(saved: unknown) {
  const entries = Array.isArray(saved) ? saved : [];
  return TRL_REFERENCE_LEVELS.map((reference, index) => {
    const entry = entries.find((item) => item && item.level === reference.level);
    const legacy = LEGACY_LEVELS[index];
    return {
      ...reference,
      label: typeof entry?.label === "string" && entry.label.trim() && entry.label !== legacy?.[0]
        && !(reference.level === 7 && entry.label === "실환경 신뢰성 검증")
        && !(reference.level === 5 && entry.label === "시작품 성능 평가")
        ? entry.label : reference.label,
      description: typeof entry?.description === "string" && entry.description.trim() && entry.description !== legacy?.[1]
        ? entry.description : reference.description,
    };
  });
}