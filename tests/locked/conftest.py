"""Locked tests: verified against LOCK.sha256 before anything is collected.

Every file in this directory -- this one included -- has its sha256 recorded in
LOCK.sha256 together with the git commit the lock was taken at. Collection
aborts if any file differs, if a file is present that the manifest does not
know, or if the manifest is missing. The point is not that the files cannot be
edited (they can), it is that editing them cannot be silent: a change needs a
new lock commit, which is visible in `git log -- tests/locked`.

Tests here are written before the code they judge and locked before that code
exists. scripts/locked-tests is the loud version of this check plus a git
comparison; run that rather than bare pytest when the result matters.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
MANIFEST = HERE / "LOCK.sha256"


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _tracked_files() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in HERE.rglob("*"):
        if p.is_file() and p.name != "LOCK.sha256" and "__pycache__" not in p.parts:
            out[p.relative_to(HERE).as_posix()] = _digest(p)
    return out


def _manifest() -> tuple[dict[str, str], dict[str, str]]:
    meta: dict[str, str] = {}
    want: dict[str, str] = {}
    for line in MANIFEST.read_text().splitlines():
        if line.startswith("# "):
            k, _, v = line[2:].partition(": ")
            meta[k] = v
        elif line.strip():
            h, _, name = line.partition("  ")
            want[name] = h
    return meta, want


def pytest_sessionstart(session: pytest.Session) -> None:
    if os.environ.get("JOBBOT_UNLOCKED_TESTS") == "1":
        # Only for authoring a new locked test before it is locked. The runner
        # script never sets this; it exists so `pytest tests/locked/test_x.py`
        # works while writing test_x.py, and nothing else.
        return
    if not MANIFEST.exists():
        pytest.exit("tests/locked/LOCK.sha256 is missing: run scripts/lock-tests", returncode=3)
    meta, want = _manifest()
    have = _tracked_files()
    bad = [n for n in sorted(set(want) | set(have)) if want.get(n) != have.get(n)]
    if bad:
        pytest.exit(
            "LOCKED TESTS DIFFER from lock commit "
            f"{meta.get('commit', '?')[:12]}:\n  " + "\n  ".join(bad)
            + "\nRe-lock deliberately with scripts/lock-tests; it records a new commit.",
            returncode=3,
        )


# ---------------------------------------------------------------- harness
#
# Every test gets its own data dir, profile path and server on a free loopback
# port, with the LLM pointed at the scripted fake. Nothing here can reach the
# user's real data/, config/, ~/.jobbot or Messages.


class Workspace:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.data = tmp / "data"
        self.profile = tmp / "config" / "profile.yaml"
        self.script = tmp / "fake-llm.json"
        self.llm_log = tmp / "fake-llm.log.jsonl"
        self.data.mkdir(parents=True)
        self.profile.parent.mkdir(parents=True)
        self.script.write_text("{}")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen | None = None
        self.log = tmp / "server.log"

    def env(self) -> dict[str, str]:
        e = {k: v for k, v in os.environ.items()
             if not k.startswith(("ANTHROPIC", "GEMINI", "JOBBOT_"))}
        e.update({
            "JOBBOT_LLM_PROVIDER": "fake",
            "JOBBOT_FAKE_LLM": str(self.script),
            "JOBBOT_FAKE_LLM_LOG": str(self.llm_log),
            "JOBBOT_LLM_FALLBACK": "none",
            "HOME": str(self.tmp / "home"),   # keeps ~/.jobbot out of reach
        })
        (self.tmp / "home").mkdir(exist_ok=True)
        return e

    def script_llm(self, script: dict) -> None:
        """Set what the fake model answers. Re-read by the server on every call."""
        self.script.write_text(json.dumps(script))

    def llm_calls(self) -> list[dict]:
        if not self.llm_log.exists():
            return []
        return [json.loads(l) for l in self.llm_log.read_text().splitlines() if l.strip()]

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "jobbot.cli", "--profile", str(self.profile),
             "--csv", str(self.data / "applications.csv"),
             "dashboard", "--no-open", "--port", str(self.port)],
            cwd=ROOT, env=self.env(),
            stdout=open(self.log, "w"), stderr=subprocess.STDOUT,
        )
        for _ in range(80):
            try:
                urllib.request.urlopen(self.base + "/api/status", timeout=1)
                return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.25)
        raise RuntimeError(f"server did not come up; log:\n{self.log.read_text()[-2000:]}")

    def stop(self) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def get(self, path: str) -> tuple[int, bytes, dict[str, str]]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=30) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def get_json(self, path: str) -> dict | list:
        status, body, _ = self.get(path)
        assert status == 200, f"GET {path} -> {status}: {body[:300]!r}"
        return json.loads(body)

    def post(self, path: str, body: bytes | dict, timeout: int = 60) -> dict:
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        req = urllib.request.Request(
            self.base + path, data=data, method="POST",
            headers={"Content-Type": "application/json" if isinstance(body, dict)
                     else "application/octet-stream"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read())


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    w = Workspace(tmp_path)
    w.start()
    yield w
    w.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, ws: Workspace):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda exc: errors.append(str(exc)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.errors = errors  # type: ignore[attr-defined]
    pg.ws = ws          # type: ignore[attr-defined]
    yield pg
    ctx.close()


@pytest.fixture
def phone(browser, ws: Workspace):
    """iPhone-width context: the dashboard is used over the tailnet from a phone."""
    ctx = browser.new_context(viewport={"width": 375, "height": 812},
                              device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.ws = ws  # type: ignore[attr-defined]
    yield pg
    ctx.close()
