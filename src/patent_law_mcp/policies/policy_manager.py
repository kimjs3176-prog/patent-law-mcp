"""행정규칙 및 법령 정책 테이블 매니저

지식재산처 고시, 업무편람, 세법 개정 시 YAML 설정 파일 하나만으로
MCP 서버 전체의 산출 기준과 감사 추적 메타데이터를 일괄 제어합니다.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

POLICY_DIR = Path(__file__).parent
DEFAULT_POLICY_FILE = POLICY_DIR / "kipo_notice_rules.yaml"


class PolicyManager:
    """법령 및 고시 정책 테이블을 관리하는 싱글톤 매니저"""

    _instance: Optional["PolicyManager"] = None
    _cached_policy: Optional[Dict[str, Any]] = None

    def __new__(cls) -> "PolicyManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.load_policy()
        return cls._instance

    def load_policy(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        target_path = file_path or DEFAULT_POLICY_FILE
        if not target_path.exists():
            # 파일이 없을 경우 안전한 기본값 반환
            self._cached_policy = self._default_fallback_policy()
            return self._cached_policy

        with open(target_path, "r", encoding="utf-8") as f:
            self._cached_policy = yaml.safe_load(f)
        return self._cached_policy

    @property
    def policy(self) -> Dict[str, Any]:
        if self._cached_policy is None:
            self.load_policy()
        return self._cached_policy or self._default_fallback_policy()

    @property
    def metadata(self) -> Dict[str, str]:
        return self.policy.get("metadata", {})

    @property
    def audit_trail_basis(self) -> str:
        meta = self.metadata
        return f"{meta.get('notice_id', '지식재산처고시')} ({meta.get('effective_date', '최신')} 시행 기준)"

    @property
    def unutilized_free_rules(self) -> Dict[str, Any]:
        return self.policy.get("unutilized_free_license", {})

    @property
    def exclusive_licensing_rules(self) -> Dict[str, Any]:
        return self.policy.get("exclusive_licensing", {})

    @property
    def exclusive_renewal_rules(self) -> Dict[str, Any]:
        return self.policy.get("exclusive_renewal", {})

    @property
    def disposal_compensation_rules(self) -> Dict[str, Any]:
        return self.policy.get("disposal_compensation", {})

    def _default_fallback_policy(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "notice_name": "국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령",
                "notice_id": "지식재산처고시 제2025-4호",
                "effective_date": "2025-10-30",
            },
            "unutilized_free_license": {
                "unutilized_years_threshold": 3,
                "max_free_license_years": 3,
                "sme_renewal_discount_rate": 0.02,
                "joint_patentee_written_consent_required": True,
            },
            "exclusive_licensing": {
                "minimum_royalty_amount": 3000000,
                "payment_deadline_days": 60,
                "exclusive_lump_sum_multiplier": 2.5,
                "exclusive_running_multiplier": 1.5,
            },
            "exclusive_renewal": {
                "application_deadline_days_before_expiry": 30,
                "statutory_grounds_count": 5,
            },
            "disposal_compensation": {
                "net_income_payout_ratio": 0.50,
                "tax_free_limit_annual": 7000000,
            },
        }


# 전역 싱글톤 인스턴스
policy_manager = PolicyManager()
