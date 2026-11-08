import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_upstream.py"


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@example.com", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)})


def make_upstream(tmp_path):
    repo = tmp_path / "up"
    (repo / "lib").mkdir(parents=True)
    (repo / "lib" / "rule.ts").write_text("export const A = 1;\n", encoding="utf-8")
    git("init", "-q", "-b", "main", cwd=repo)
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    manifest = tmp_path / "m" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"sources": [{
        "name": "up", "repo": "example/up", "branch": "main", "synced_commit": None,
        "files": [{"path": "lib/rule.ts", "role": "logic", "ported_to": ["src/x.py"]}],
        "watch": [{"dir": "lib", "pattern": "*.ts"}], "ignored": [],
    }]}), encoding="utf-8")
    return repo, manifest


def run(manifest, repo, *mode):
    return subprocess.run([sys.executable, str(SCRIPT), *mode, "--manifest", str(manifest), "--source-dir", f"up={repo}"],
                          capture_output=True, text=True)


def test_update_then_check_detects_changes_and_new_files(tmp_path):
    repo, manifest = make_upstream(tmp_path)
    assert run(manifest, repo, "--update").returncode == 0
    assert run(manifest, repo, "--check").returncode == 0

    (repo / "lib" / "rule.ts").write_text("export const A = 2;\n", encoding="utf-8")
    (repo / "lib" / "newRule.ts").write_text("export const B = 1;\n", encoding="utf-8")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "change", cwd=repo)
    r = run(manifest, repo, "--check")
    assert r.returncode == 1
    assert "**변경** `lib/rule.ts`" in r.stdout and "src/x.py" in r.stdout
    assert "-export const A = 1;" in r.stdout and "+export const A = 2;" in r.stdout
    assert "**새 파일** `lib/newRule.ts`" in r.stdout
