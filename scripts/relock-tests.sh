#!/bin/zsh
# Regenerate tests/locked/LOCK.sha256 after a deliberate, reviewed change to a
# locked test. The lock exists so tests cannot be quietly weakened — only run
# this when you can name why the assertion legitimately changed.

set -e
ROOT=${0:a:h:h}
cd "$ROOT"

print "current lock:"
head -3 tests/locked/LOCK.sha256 2>/dev/null | sed 's/^/  /'

print "\nchanged locked tests vs HEAD:"
git diff --name-only HEAD -- tests/locked/ | grep -v LOCK.sha256 | sed 's/^/  /' || print "  (none)"

.venv/bin/python - <<'PY'
import hashlib, subprocess
from pathlib import Path
here = Path("tests/locked")
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
files = sorted(p for p in here.rglob("*")
               if p.is_file() and p.name != "LOCK.sha256" and "__pycache__" not in p.parts)
lines = [f"# commit: {commit}",
         "# author: relock-tests.sh",
         f"# date: {subprocess.run(['date','+%Y-%m-%d'],capture_output=True,text=True).stdout.strip()}"]
for p in files:
    lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(here)}")
(here / "LOCK.sha256").write_text("\n".join(lines) + "\n")
print(f"\nrelocked {len(files)} files at {commit}")
PY

print "\nverifying lock holds:"
.venv/bin/pytest tests/locked/ -q 2>&1 | tail -3
