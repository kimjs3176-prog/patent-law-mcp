"""법령·고시·기관 규정 정책 테이블 매니저 (기관 유형별 프로파일)

프로파일
- national: 국유특허 (국가공무원 등 직무발명 규정·지식재산처 고시) — kipo_notice_rules.yaml
- public_research: 대학 산학협력단·정부출연연구기관 (기술이전법·발명진흥법·기관 규정) — public_research.yaml
- private_company: 민간 기업 (발명진흥법 직무발명 보상·사내 규정) — private_company.yaml

기본 프로파일은 환경변수 PATENT_LAW_MCP_PROFILE(기본 national)로, 파일 자체는 PATENT_LAW_MCP_POLICY_FILE로 바꿀 수 있습니다.
도구마다 profile 인자로 호출 단위 선택도 됩니다. 파일이 바뀌면 다음 조회 때 자동으로 다시 읽고,
필수 키가 없거나 형식이 틀리면 PolicyError를 냅니다 (코드 안에 별도 기본값 없음).
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml

POLICY_DIR = Path(__file__).parent
DEFAULT_POLICY_FILE = POLICY_DIR / "kipo_notice_rules.yaml"
PROFILE_FILES = {
    "national": DEFAULT_POLICY_FILE,
    "public_research": POLICY_DIR / "public_research.yaml",
    "private_company": POLICY_DIR / "private_company.yaml",
}
ProfileName = Literal["national", "public_research", "private_company"]
_NUM = (int, float)
_OPT_NUM = (int, float, type(None))

COMMON_SCHEMA: Dict[str, Dict[str, tuple]] = {
    "metadata": {"profile_type": (str,), "notice_name": (str,), "notice_id": (str,), "effective_date": (str,), "parent_regulation": (str,)},
    "articles": {"disposal_compensation": (str,), "exclusive_license_registration": (str,), "tax_free_limit": (str,)},
    "contract_practice": {
        "due_diligence_years": (int,),
        "sales_report_deadline_days": (int,),
        "exclusive_lump_sum_multiplier": _NUM,
        "exclusive_running_multiplier": _NUM,
        "reference_rates_by_scale": (dict,),
    },
    "disposal_compensation": {"payout_ratio": _OPT_NUM, "deduct_direct_expenses": (bool,), "deductible_items": (list,)},
    "income_tax": {"tax_free_limit_annual": (int,), "retired_withholding_rate": _NUM, "local_income_tax_ratio": _NUM},
}

NATIONAL_SCHEMA: Dict[str, Dict[str, tuple]] = {
    "articles": {
        k: (str,)
        for k in (
            "free_license", "joint_patentee_consent", "licensee_limit", "free_license_paid_conversion",
            "sme_renewal_rate", "exclusive_minimum_royalty", "exclusive_renewal", "exclusive_competitive_bidding",
            "non_exclusive_private_contract", "free_disposal_grounds", "exclusive_renewal_private_contract",
            "registration_compensation",
        )
    },
    "unutilized_free_license": {
        "unutilized_years_threshold": (int,),
        "max_free_license_years": (int,),
        "sme_renewal_base_rate": _NUM,
        "joint_patentee_written_consent_required": (bool,),
    },
    "exclusive_licensing": {
        "minimum_royalty_amount": (int,),
        "payment_deadline_days": (int,),
        "competitive_bidding_required": (bool,),
        "private_contract_exceptions": (list,),
    },
    "exclusive_renewal": {"application_deadline_days_before_expiry": (int,), "grounds": (dict,)},
    "registration_compensation": {"patent": (int,), "utility_model": (int,), "design": (int,)},
}

INSTITUTION_SCHEMA: Dict[str, Dict[str, tuple]] = {
    "articles": {"invention_report": (str,), "succession_notice": (str,)},
    "invention_procedure": {"succession_notice_months": (int,)},
}
REQUIRED_SCALES = ("farmer", "sme", "middle", "large")


class PolicyError(RuntimeError):
    """정책 YAML이 없거나 필수 항목이 빠졌을 때"""


def _check(policy: dict, schema: Dict[str, Dict[str, tuple]], errors: List[str]) -> None:
    for section, keys in schema.items():
        body = policy.get(section)
        if not isinstance(body, dict):
            errors.append(f"'{section}' 섹션이 없습니다.")
            continue
        for key, types in keys.items():
            if key not in body:
                errors.append(f"'{section}.{key}' 항목이 없습니다.")
                continue
            value = body[key]
            # bool은 int의 하위 타입이므로 숫자 자리에 true/false가 들어오는 것을 막는다
            if not isinstance(value, types) or (bool not in types and isinstance(value, bool)):
                errors.append(f"'{section}.{key}' 값의 형식이 틀립니다 (현재: {value!r}).")


def validate_policy(policy: Any) -> List[str]:
    """누락·형식 오류 목록을 반환합니다 (빈 목록이면 정상)."""
    if not isinstance(policy, dict):
        return ["최상위가 매핑(dict)이 아닙니다."]
    errors: List[str] = []
    _check(policy, COMMON_SCHEMA, errors)
    profile = (policy.get("metadata") or {}).get("profile_type")
    if profile == "national":
        _check(policy, NATIONAL_SCHEMA, errors)
    elif profile in ("public_research", "private_company"):
        _check(policy, INSTITUTION_SCHEMA, errors)
    else:
        errors.append(f"metadata.profile_type은 national·public_research·private_company 중 하나여야 합니다 (현재: {profile!r}).")
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
        env_file = os.environ.get("PATENT_LAW_MCP_POLICY_FILE")
        if env_file:
            return Path(env_file)
        profile = os.environ.get("PATENT_LAW_MCP_PROFILE", "national")
        if profile not in PROFILE_FILES:
            raise PolicyError(f"PATENT_LAW_MCP_PROFILE은 {', '.join(PROFILE_FILES)} 중 하나여야 합니다 (현재: {profile!r}).")
        return PROFILE_FILES[profile]

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
    def profile(self) -> str:
        return self.metadata["profile_type"]

    @property
    def is_national(self) -> bool:
        return self.profile == "national"

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
            "profile": self.profile,
            "notice": self.audit_trail_basis,
            "parent_regulation": self.metadata["parent_regulation"],
            "policy_file": str(self.path),
            "unverified_items": self.verification_notes,
        }

    def require_national(self, feature: str) -> None:
        if not self.is_national:
            raise ValueError(f"{feature}은(는) 국유특허(national) 프로파일 전용 기능입니다 (현재 프로파일: {self.profile}).")


policy_manager = PolicyManager()
_profile_managers: Dict[str, PolicyManager] = {}


def policy_for(profile: Optional[str] = None) -> PolicyManager:
    """profile이 없으면 기본 매니저(환경변수 기준), 있으면 해당 프로파일 파일의 매니저를 돌려줍니다."""
    if profile is None:
        return policy_manager
    if profile not in PROFILE_FILES:
        raise ValueError(f"profile은 {', '.join(PROFILE_FILES)} 중 하나여야 합니다 (입력: {profile!r}).")
    if profile not in _profile_managers:
        _profile_managers[profile] = PolicyManager(PROFILE_FILES[profile])
    return _profile_managers[profile]


def get_policy_table(profile: Optional[ProfileName] = None) -> Dict[str, Any]:
    """적용 중인 기준값 표(정책 YAML)와 근거 조항, 원문 확인이 필요한 항목을 보여 줍니다.

    Args:
        profile: "national"(국유특허), "public_research"(대학·출연연), "private_company"(민간 기업). 비우면 기본 프로파일
    """
    pm = policy_for(profile)
    return {
        "policy_file": str(pm.path),
        "available_profiles": list(PROFILE_FILES),
        "how_to_update": "이 파일의 값을 고치면 다음 도구 호출부터 반영됩니다 (서버 재시작 불필요).",
        **pm.policy,
    }
