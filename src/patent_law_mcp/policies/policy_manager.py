"""법령·고시 정책 테이블 매니저

- YAML 한 파일(기본: kipo_notice_rules.yaml, 환경변수 PATENT_LAW_MCP_POLICY_FILE로 변경)이 유일한 기준값 출처입니다.
- 파일 수정 시각이 바뀌면 다음 조회 때 자동으로 다시 읽습니다 (서버 재시작 불필요).
- 필수 키가 없거나 형식이 틀리면 PolicyError를 냅니다. 코드 안에 별도 기본값을 두지 않습니다.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

POLICY_DIR = Path(__file__).parent
DEFAULT_POLICY_FILE = POLICY_DIR / "kipo_notice_rules.yaml"

# 섹션 -> {키: 허용 타입}
REQUIRED_SCHEMA: Dict[str, Dict[str, tuple]] = {
    "metadata": {"notice_name": (str,), "notice_id": (str,), "effective_date": (str,), "parent_regulation": (str,)},
    "articles": {
        k: (str,)
        for k in (
            "free_license", "joint_patentee_consent", "licensee_limit", "free_license_paid_conversion",
            "sme_renewal_rate", "exclusive_minimum_royalty", "exclusive_renewal", "disposal_compensation",
            "exclusive_competitive_bidding", "non_exclusive_private_contract", "free_disposal_grounds",
            "exclusive_license_registration", "tax_free_limit", "exclusive_renewal_private_contract",
            "registration_compensation",
        )
    },
    "unutilized_free_license": {
        "unutilized_years_threshold": (int,),
        "max_free_license_years": (int,),
        "sme_renewal_base_rate_reduction_pp": (int, float),
        "joint_patentee_written_consent_required": (bool,),
    },
    "exclusive_licensing": {
        "minimum_royalty_amount": (int,),
        "payment_deadline_days": (int,),
        "competitive_bidding_required": (bool,),
    },
    "contract_practice": {
        "due_diligence_years": (int,),
        "sales_report_deadline_days": (int,),
        "exclusive_lump_sum_multiplier": (int, float),
        "exclusive_running_multiplier": (int, float),
        "reference_rates_by_scale": (dict,),
    },
    "exclusive_renewal": {"application_deadline_days_before_expiry": (int,)},
    "registration_compensation": {"patent": (int,), "utility_model": (int,), "design": (int,)},
    "disposal_compensation": {"payout_ratio": (int, float), "deduct_direct_expenses": (bool,), "deductible_items": (list,)},
    "income_tax": {
        "tax_free_limit_annual": (int,),
        "retired_withholding_rate": (int, float),
        "local_income_tax_ratio": (int, float),
    },
}
REQUIRED_SCALES = ("farmer", "sme", "middle", "large")


class PolicyError(RuntimeError):
    """정책 YAML이 없거나 필수 항목이 빠졌을 때"""


def validate_policy(policy: Any) -> List[str]:
    """누락·형식 오류 목록을 반환합니다 (빈 목록이면 정상)."""
    if not isinstance(policy, dict):
        return ["최상위가 매핑(dict)이 아닙니다."]
    errors = []
    for section, keys in REQUIRED_SCHEMA.items():
        body = policy.get(section)
        if not isinstance(body, dict):
            errors.append(f"'{section}' 섹션이 없습니다.")
            continue
        for key, types in keys.items():
            value = body.get(key)
            # bool은 int의 하위 타입이므로 int 자리에 true/false가 들어오는 것을 막는다
            if value is None or not isinstance(value, types) or (bool not in types and isinstance(value, bool)):
                errors.append(f"'{section}.{key}' 값이 없거나 형식이 틀립니다 (현재: {value!r}).")
    rates = (policy.get("contract_practice") or {}).get("reference_rates_by_scale") or {}
    for scale in REQUIRED_SCALES:
        entry = rates.get(scale) if isinstance(rates, dict) else None
        if not isinstance(entry, dict) or not {"lump_sum", "running_rate", "description"} <= set(entry):
            errors.append(f"'contract_practice.reference_rates_by_scale.{scale}'에 lump_sum·running_rate·description이 필요합니다.")
    return errors


class PolicyManager:
    def __init__(self, file_path: Optional[Path] = None):
        self._explicit_path = Path(file_path) if file_path else None
        self._policy: Optional[Dict[str, Any]] = None
        self._loaded_key: Optional[tuple] = None

    @property
    def path(self) -> Path:
        if self._explicit_path:
            return self._explicit_path
        env = os.environ.get("PATENT_LAW_MCP_POLICY_FILE")
        return Path(env) if env else DEFAULT_POLICY_FILE

    def load(self) -> Dict[str, Any]:
        path = self.path
        if not path.exists():
            raise PolicyError(f"정책 파일이 없습니다: {path}")
        with open(path, "r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
        errors = validate_policy(policy)
        if errors:
            raise PolicyError(f"정책 파일 오류 ({path}):\n- " + "\n- ".join(errors))
        self._policy = policy
        self._loaded_key = (str(path), path.stat().st_mtime_ns)
        return policy

    @property
    def policy(self) -> Dict[str, Any]:
        path = self.path
        key = (str(path), path.stat().st_mtime_ns) if path.exists() else None
        if self._policy is None or key != self._loaded_key:
            self.load()
        return self._policy  # type: ignore[return-value]

    def section(self, name: str) -> Dict[str, Any]:
        return self.policy[name]

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.section("metadata")

    @property
    def articles(self) -> Dict[str, str]:
        return self.section("articles")

    @property
    def verification_notes(self) -> List[str]:
        return list(self.policy.get("verification_notes") or [])

    @property
    def audit_trail_basis(self) -> str:
        meta = self.metadata
        return f"{meta['notice_id']} ({meta['effective_date']} 시행 기준)"

    def audit_block(self) -> Dict[str, Any]:
        """도구 출력에 붙이는 근거·검증 상태 메타데이터"""
        return {
            "notice": self.audit_trail_basis,
            "parent_regulation": self.metadata["parent_regulation"],
            "policy_file": str(self.path),
            "unverified_items": self.verification_notes,
        }


policy_manager = PolicyManager()


def get_policy_table() -> Dict[str, Any]:
    """현재 적용 중인 법령·고시 기준값 표(정책 YAML)와 근거 조항, 원문 확인이 필요한 항목을 보여 줍니다."""
    policy = policy_manager.policy
    return {
        "policy_file": str(policy_manager.path),
        "how_to_update": "이 파일의 값을 고치면 다음 도구 호출부터 반영됩니다 (서버 재시작 불필요).",
        **policy,
    }
