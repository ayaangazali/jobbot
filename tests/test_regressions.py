"""Guards for bugs that failed silently.

Each of these shipped as a wrong answer or a skipped posting rather than a
crash, which is why they need a test at all: nothing in a normal run surfaces
them. Every assertion here fails on the unfixed code.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from jobbot.ats.detect import ATS
from jobbot.discovery.sources import JobPost
from jobbot.llm.client import _is_quota_exhausted, _is_transient
from jobbot.orchestrator import fit_score
from jobbot.profile import Profile

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def profile() -> Profile:
    return Profile.model_validate(
        yaml.safe_load((ROOT / "config" / "profile.example.yaml").read_text())
    )


def _post(**kw) -> JobPost:
    base = dict(ats=ATS.WORKDAY, native_id="1", company="Acme",
                title="Software Engineer", url="https://example.com")
    return JobPost(**{**base, **kw})


def test_description_less_posting_is_not_filtered_out(profile: Profile) -> None:
    """Workday's search API returns no description; that must not filter.

    Unfixed, the skills component scored 0 against a bare title and every
    Workday posting landed at 0.4 -- under the 0.5 default threshold.
    """
    assert fit_score(profile, _post(description="")) >= 0.5


def test_description_still_drives_the_score(profile: Profile) -> None:
    """The no-description branch must not flatten real scoring."""
    matching = _post(ats=ATS.GREENHOUSE,
                     description="We use Python, Go, PostgreSQL, Docker, Redis.")
    unrelated = _post(ats=ATS.GREENHOUSE, title="Veterinary Technician",
                      description="Animal husbandry and clinic scheduling.")
    assert fit_score(profile, matching) > fit_score(profile, unrelated)
    assert fit_score(profile, unrelated) < 0.5


def test_plain_429_is_transient_not_quota_exhaustion() -> None:
    """An ordinary per-minute 429 must stay retryable.

    Unfixed, `rate_limit_error` counted as exhaustion, which flipped the run to
    the fallback backend permanently on the first burst of concurrency.
    """
    exc = Exception(
        "Error code: 429 - {'type': 'error', 'error': "
        "{'type': 'rate_limit_error', 'message': 'rate limit exceeded'}}"
    )
    assert not _is_quota_exhausted(exc)
    assert _is_transient(exc)


def test_real_exhaustion_still_detected() -> None:
    assert _is_quota_exhausted(Exception("You are out of extra usage credits"))
    assert _is_quota_exhausted(Exception("Quota exceeded for this window"))


@pytest.mark.parametrize("label", [
    "Bachelor's Degree",
    "I don't wish to answer",
    'He said "yes"',
    "Yes",
])
def test_selector_quoting_survives_apostrophes(label: str) -> None:
    """Option text goes into selectors; employer text contains apostrophes.

    Unfixed, `label:has-text('Bachelor's Degree')` was unparseable, all three
    radio fallbacks threw identically, and the field was left blank.
    """
    from jobbot.forms.fill import q      # imported here so the other guards
                                        # still collect on unfixed code
    quoted = q(label)
    assert quoted.startswith('"') and quoted.endswith('"')
    # The quoted form must round-trip to the original label exactly, or we
    # would be clicking an option that does not exist.
    import json
    assert json.loads(quoted) == label
