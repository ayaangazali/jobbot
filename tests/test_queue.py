"""The queue decides what gets applied to, so its two dangerous mistakes get a test.

Applying to a blacklisted job means a second application to an employer the
candidate already approached personally. Losing an approval means a run that
silently does nothing. Both are silent failures, so both are pinned here.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobbot.discovery.sources import ATS
from jobbot.queue import JobQueue


@dataclass
class FakePost:
    native_id: str
    company: str = "acme"
    title: str = "Engineer"
    url: str = "https://example.com/j"
    location: str = "Remote"
    ats: ATS = ATS.GREENHOUSE

    @property
    def job_id(self) -> str:
        return f"{self.ats.value}:{self.native_id}"


def test_a_decision_survives_rediscovery(tmp_path) -> None:
    """Discovery runs again every time; it must not clear what was decided."""
    q = JobQueue(tmp_path / "queue.json")
    q.add_posts([FakePost("1"), FakePost("2")])
    q.decide_many({"greenhouse:1": "blacklist", "greenhouse:2": "approved"})

    # same jobs come back from a later discovery, with an edited title
    again = JobQueue(tmp_path / "queue.json")
    again.add_posts([FakePost("1", title="Engineer II"), FakePost("2"), FakePost("3")])

    assert again.blacklisted_ids() == {"greenhouse:1"}, \
        "a job the candidate is handling themselves must stay blacklisted"
    assert again.approved_ids() == {"greenhouse:2"}
    assert again.get("greenhouse:1").title == "Engineer II", "the posting still refreshes"
    assert again.get("greenhouse:3").decision == "pending", "new jobs are not opted in"


def test_nothing_is_approved_by_default(tmp_path) -> None:
    """An empty tick list means apply to nothing, never apply to everything."""
    q = JobQueue(tmp_path / "queue.json")
    q.add_posts([FakePost(str(i)) for i in range(5)])
    assert q.approved_ids() == set()


def test_an_unknown_decision_is_refused(tmp_path) -> None:
    q = JobQueue(tmp_path / "queue.json")
    q.add_posts([FakePost("1")])
    assert not q.decide("greenhouse:1", "yolo")
    assert q.get("greenhouse:1").decision == "pending"


def test_a_corrupt_file_does_not_silently_start_empty(tmp_path) -> None:
    """Starting from empty would rewrite every decision away on the next save."""
    p = tmp_path / "queue.json"
    p.write_text("{not json")
    try:
        JobQueue(p)
    except RuntimeError as exc:
        assert "unreadable" in str(exc)
    else:
        raise AssertionError("a corrupt queue must refuse to load, not reset")
