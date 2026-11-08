"""조회 결과 로컬 캐시 (SQLite)

- 위치: 환경변수 PATENT_LAW_MCP_CACHE (파일 경로, 또는 "off"로 끄기). 기본 ~/.cache/patent-law-mcp/cache.sqlite3
- 보관 기간: PATENT_LAW_MCP_CACHE_TTL_HOURS (기본 168시간 = 7일). 네임스페이스별로 더 짧게 지정 가능
- 성공한 조회만 저장합니다 (실패·found=False는 저장하지 않음).
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _path() -> Optional[Path]:
    value = os.environ.get("PATENT_LAW_MCP_CACHE", "").strip()
    if value.lower() in ("off", "0", "false", "none", "no"):
        return None
    if value:
        return Path(value).expanduser()
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "patent-law-mcp" / "cache.sqlite3"


def _ttl_seconds(ttl_hours: Optional[float]) -> float:
    default = float(os.environ.get("PATENT_LAW_MCP_CACHE_TTL_HOURS", "168"))
    return (min(ttl_hours, default) if ttl_hours is not None else default) * 3600


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("CREATE TABLE IF NOT EXISTS cache (ns TEXT, key TEXT, stored REAL, value TEXT, PRIMARY KEY (ns, key))")
    return conn


def get(ns: str, key: str, ttl_hours: Optional[float] = None) -> Optional[Dict[str, Any]]:
    path = _path()
    if not path or not path.exists():
        return None
    try:
        with _connect(path) as conn:
            row = conn.execute("SELECT stored, value FROM cache WHERE ns = ? AND key = ?", (ns, key)).fetchone()
    except sqlite3.Error:
        return None
    if not row or time.time() - row[0] > _ttl_seconds(ttl_hours):
        return None
    value = json.loads(row[1])
    value["cache"] = {"hit": True, "stored_at": datetime.fromtimestamp(row[0], timezone.utc).isoformat(timespec="seconds")}
    return value


def put(ns: str, key: str, value: Dict[str, Any]) -> None:
    path = _path()
    if not path:
        return
    try:
        with _connect(path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (ns, key, stored, value) VALUES (?, ?, ?, ?)",
                (ns, key, time.time(), json.dumps({k: v for k, v in value.items() if k != "cache"}, ensure_ascii=False)),
            )
    except sqlite3.Error:
        pass
