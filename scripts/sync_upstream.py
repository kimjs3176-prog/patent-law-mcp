#!/usr/bin/env python3
"""업스트림(patent-summary-wizard, patent-video-skill) 변경 감지·기준선 갱신 스크립트 (표준 라이브러리만 사용)

  python3 scripts/sync_upstream.py --check [--report drift.md] [--json]
      upstream/manifest.json에 기록된 기준선과 각 저장소 최신 커밋을 비교합니다.
      종료 코드: 0 = 동기화 상태, 1 = 업스트림 변경 있음(포팅 필요), 2 = 오류
  python3 scripts/sync_upstream.py --update
      포팅을 끝낸 뒤 실행: 최신 업스트림 파일을 upstream/snapshots/에 저장하고 매니페스트 기준선을 갱신합니다.
  --source-dir NAME=PATH  이미 받아 둔 체크아웃을 사용 (예: patent-video-skill=../patent-video-skill)
"""

import argparse
import datetime as dt
import difflib
import fnmatch
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "upstream" / "manifest.json"
SNAPSHOTS = ROOT / "upstream" / "snapshots"
MAX_DIFF_LINES = 400


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checkout(source: dict, workdir: Path, local_dirs: Dict[str, Path]) -> Path:
    if source["name"] in local_dirs:
        return local_dirs[source["name"]]
    dest = workdir / source["name"]
    url = f"https://github.com/{source['repo']}.git"
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", "--branch", source["branch"], url, str(dest)],
        check=True,
        env={"GIT_LFS_SKIP_SMUDGE": "1", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(workdir)},
    )
    return dest


def head_commit(repo_dir: Path) -> str:
    return subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def watched_files(repo_dir: Path, watch: List[dict]) -> List[str]:
    found = set()
    for w in watch:
        base = repo_dir / w["dir"]
        if base.is_dir():
            for p in base.iterdir():
                if p.is_file() and fnmatch.fnmatch(p.name, w["pattern"]):
                    found.add(str(p.relative_to(repo_dir)))
    return sorted(found)


def compare(source: dict, repo_dir: Path) -> dict:
    tracked = {f["path"]: f for f in source["files"]}
    ignored = {i["path"] for i in source.get("ignored", [])}
    changed, missing = [], []
    for path, entry in tracked.items():
        f = repo_dir / path
        if not f.exists():
            missing.append(path)
            continue
        data = f.read_bytes()
        if sha256(data) != entry.get("sha256"):
            snap = SNAPSHOTS / source["name"] / path
            old = snap.read_text(encoding="utf-8", errors="replace").splitlines() if snap.exists() else []
            new = data.decode("utf-8", errors="replace").splitlines()
            diff = list(difflib.unified_diff(old, new, f"synced/{path}", f"latest/{path}", lineterm=""))
            changed.append({"path": path, "role": entry.get("role"), "ported_to": entry.get("ported_to", []), "diff": diff})
    new_files = [p for p in watched_files(repo_dir, source.get("watch", [])) if p not in tracked and p not in ignored]
    return {
        "name": source["name"],
        "repo": source["repo"],
        "synced_commit": source.get("synced_commit"),
        "latest_commit": head_commit(repo_dir),
        "changed": changed,
        "missing": missing,
        "new_files": new_files,
    }


def render(results: List[dict]) -> str:
    lines = ["# 업스트림 변경 감지 보고", ""]
    drift = any(r["changed"] or r["missing"] or r["new_files"] for r in results)
    lines.append("포팅이 필요한 변경이 있습니다." if drift else "모든 추적 파일이 기준선과 같습니다.")
    lines.append("")
    for r in results:
        synced = (r["synced_commit"] or "없음")[:7]
        lines.append(f"## {r['repo']} (`{synced}` → `{r['latest_commit'][:7]}`)")
        if not (r["changed"] or r["missing"] or r["new_files"]):
            lines += ["변경 없음", ""]
            continue
        for c in r["changed"]:
            targets = ", ".join(f"`{t}`" for t in c["ported_to"]) or "(대상 없음)"
            lines.append(f"- **변경** `{c['path']}` ({c['role']}) → 반영 대상: {targets}")
        for m in r["missing"]:
            lines.append(f"- **삭제·이동** `{m}` — 업스트림에서 사라졌습니다. 매니페스트를 고치십시오.")
        for n in r["new_files"]:
            lines.append(f"- **새 파일** `{n}` — 포팅 대상이면 files에, 아니면 ignored에 사유와 함께 추가하십시오.")
        lines.append("")
        for c in r["changed"]:
            body = c["diff"][:MAX_DIFF_LINES]
            more = len(c["diff"]) - len(body)
            lines += [f"<details><summary>diff: {c['path']}</summary>", "", "```diff", *body]
            if more > 0:
                lines.append(f"... ({more}줄 생략)")
            lines += ["```", "", "</details>", ""]
    lines += [
        "## 반영 절차",
        "1. 변경된 업스트림 로직을 반영 대상 Python 모듈에 옮기고, 업스트림 테스트 변경은 `tests/test_upstream_parity.py`에 옮긴다.",
        "2. `uv run pytest -q` 통과 확인",
        "3. `python3 scripts/sync_upstream.py --update`로 기준선 갱신 후 커밋",
    ]
    return "\n".join(lines) + "\n"


def update(manifest: dict, source: dict, repo_dir: Path) -> None:
    for entry in source["files"]:
        src = repo_dir / entry["path"]
        if not src.exists():
            raise SystemExit(f"업스트림에 없는 추적 파일: {source['name']}/{entry['path']} (매니페스트를 먼저 고치십시오)")
        dest = SNAPSHOTS / source["name"] / entry["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        entry["sha256"] = sha256(src.read_bytes())
    source["synced_commit"] = head_commit(repo_dir)
    source["synced_at"] = dt.date.today().isoformat()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--update", action="store_true")
    ap.add_argument("--report", type=Path, help="마크다운 보고서 저장 경로")
    ap.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    ap.add_argument("--source-dir", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--manifest", type=Path, default=MANIFEST, help="매니페스트 경로 (스냅샷은 같은 폴더의 snapshots/)")
    args = ap.parse_args(argv)

    global SNAPSHOTS
    manifest_path = args.manifest.resolve()
    SNAPSHOTS = manifest_path.parent / "snapshots"

    local_dirs = {}
    for item in args.source_dir:
        name, _, path = item.partition("=")
        local_dirs[name] = Path(path).resolve()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            repos = {s["name"]: checkout(s, Path(tmp), local_dirs) for s in manifest["sources"]}
            if args.update:
                for s in manifest["sources"]:
                    update(manifest, s, repos[s["name"]])
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("기준선을 갱신했습니다:", ", ".join(f"{s['name']}@{s['synced_commit'][:7]}" for s in manifest["sources"]))
                return 0
            results = [compare(s, repos[s["name"]]) for s in manifest["sources"]]
    except (subprocess.CalledProcessError, OSError, KeyError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2

    report = render(results)
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    if args.json:
        print(json.dumps([{k: v for k, v in r.items()} for r in results], ensure_ascii=False, indent=2))
    else:
        print(report)
    return 1 if any(r["changed"] or r["missing"] or r["new_files"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
