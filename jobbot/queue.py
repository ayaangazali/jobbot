"""The shortlist: which discovered jobs the candidate has actually approved.

Discovery finds hundreds of postings and the fit filter ranks them, but neither
is a decision. This holds the decision -- one per job, made by a person -- and
the run loop applies to nothing that is not marked `approved`.

Four states, and the distinction between the last two matters:

  pending    discovered, not looked at yet
  approved   apply to this one
  blacklist  never apply -- the candidate is handling it personally
  applied    already sent, recorded so the list stops offering it

`blacklist` is not "rejected". A job the candidate applied to themselves must
never be applied to again by this software, and that has to survive a fresh
discovery run, which is why it is stored here rather than inferred from the
tracker.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import structlog

log = structlog.get_logger(__name__)

DECISIONS = ("pending", "approved", "blacklist", "applied")


@dataclass
class QueueEntry:
    job_id: str
    company: str = ""
    title: str = ""
    url: str = ""
    location: str = ""
    ats: str = ""
    decision: str = "pending"
    fit: float = 0.0
    discovered_at: str = ""
    decided_at: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JobQueue:
    """A JSON file of decisions, keyed by job id."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, QueueEntry] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text() or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            # A corrupt queue must not wipe the candidate's decisions on the
            # next write, so refuse to start from empty.
            raise RuntimeError(f"job queue at {self.path} is unreadable: {exc}") from exc
        for jid, d in raw.items():
            known = {k: v for k, v in d.items() if k in QueueEntry.__annotations__}
            self._entries[jid] = QueueEntry(**{**known, "job_id": jid})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(
            {k: v.to_dict() for k, v in self._entries.items()}, indent=1))
        tmp.replace(self.path)

    # -- reading ----------------------------------------------------------

    def all(self) -> list[QueueEntry]:
        return sorted(self._entries.values(),
                      key=lambda x: (x.decision != "approved", -x.fit, x.company))

    def get(self, job_id: str) -> QueueEntry | None:
        return self._entries.get(job_id)

    def approved_ids(self) -> set[str]:
        return {k for k, v in self._entries.items() if v.decision == "approved"}

    def blacklisted_ids(self) -> set[str]:
        return {k for k, v in self._entries.items() if v.decision == "blacklist"}

    def counts(self) -> dict[str, int]:
        out = {d: 0 for d in DECISIONS}
        for v in self._entries.values():
            out[v.decision] = out.get(v.decision, 0) + 1
        return out

    # -- writing ----------------------------------------------------------

    def add_posts(self, posts: Iterable[Any], fits: dict[str, float] | None = None) -> int:
        """Record newly discovered postings as pending. Never touch a decision."""
        fits = fits or {}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        added = 0
        for p in posts:
            jid = p.job_id
            if jid in self._entries:
                # Refresh what the posting says, keep what the candidate said.
                cur = self._entries[jid]
                cur.title, cur.company, cur.url = p.title, p.company, p.url
                cur.location = p.location or cur.location
                if jid in fits:
                    cur.fit = round(fits[jid], 3)
                continue
            self._entries[jid] = QueueEntry(
                job_id=jid, company=p.company, title=p.title, url=p.url,
                location=p.location or "", ats=p.ats.value,
                fit=round(fits.get(jid, 0.0), 3), discovered_at=now)
            added += 1
        if added or posts:
            self.save()
        return added

    def decide(self, job_id: str, decision: str, *, note: str = "") -> bool:
        if decision not in DECISIONS:
            return False
        cur = self._entries.get(job_id)
        if cur is None:
            cur = self._entries[job_id] = QueueEntry(job_id=job_id)
        cur.decision = decision
        cur.decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if note:
            cur.note = note[:300]
        return True

    def decide_many(self, decisions: dict[str, str]) -> int:
        n = sum(1 for jid, d in decisions.items() if self.decide(jid, d))
        if n:
            self.save()
        return n
