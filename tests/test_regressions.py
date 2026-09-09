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


def test_a_mid_stream_overload_is_retried_not_fatal() -> None:
    """The exact object the SDK raises for an `error` event during streaming.

    The HTTP response was a 200 -- the error arrived inside the stream -- so
    the SDK builds a generic APIStatusError with status_code=200. Trusting that
    status over the body classified an Anthropic overload as permanent: zero
    retries, and a real application marked failed seven seconds after the
    resume had rendered.
    """
    import anthropic
    import httpx

    from jobbot.llm.client import _is_quota_exhausted, _is_transient

    body = {"type": "error", "request_id": "req_x",
            "error": {"type": "overloaded_error", "message": "Overloaded"}}
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    client = anthropic.Anthropic(api_key="test")
    exc = client._make_status_error(f"{body}", body=body, response=httpx.Response(200, request=req))
    assert type(exc).__name__ == "APIStatusError" and exc.status_code == 200
    assert _is_transient(exc), "an overload must be retried"
    assert not _is_quota_exhausted(exc), "and must not flip the run to the fallback"

    # a genuine client error on the same path stays permanent
    bad = client._make_status_error(
        "{'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'bad'}}",
        body={}, response=httpx.Response(400, request=req))
    assert not _is_transient(bad)


def test_a_closed_dropdowns_placeholder_is_not_an_option() -> None:
    """Greenhouse's react-select reports exactly one option from the closed DOM:
    "Select...". Matching a confirmed answer against that list fails every time,
    so 8 of 11 blockers on a real form were "'Yes' matches none of
    ['Select...']" -- fields the fill layer opens and matches live anyway.
    """
    from jobbot.forms.model import FieldKind, FieldOption, FormField
    from jobbot.healer.answer import deterministic_answers, real_options
    from jobbot.forms.model import ParsedForm
    from jobbot.profile import Profile

    closed = FormField("q1", "Do you require visa sponsorship?", FieldKind.COMBOBOX,
                       required=True, options=[FieldOption("Select...")])
    assert real_options(closed) == []
    real = FormField("q2", "Veteran Status", FieldKind.SELECT,
                     options=[FieldOption("Select..."), FieldOption("Yes"), FieldOption("No")])
    assert real_options(real) == ["Yes", "No"], "a placeholder mixed into real options is dropped"

    prof = Profile.model_validate({
        "identity": {"first_name": "J", "last_name": "D", "email": "j@d.com"},
        "screening": {"requires_sponsorship_now": False,
                      "requires_sponsorship_future": False, "veteran_status": "No"},
    })
    answers, leftover = deterministic_answers(prof, ParsedForm(fields=[closed, real]))
    by = {a.field_id: a for a in answers}
    assert by["q1"].value == "No" and not by["q1"].needs_human, \
        "unknown options: pass the conventional word through for fill time"
    assert by["q2"].value == "No" and not by["q2"].needs_human
    assert leftover == []


def test_sponsorship_now_and_future_are_different_questions() -> None:
    """Both wordings are verbatim from a live Greenhouse form.

    A candidate on OPT answers now=No, future=Yes. The old first pattern
    matched `require.*visa.*sponsor` and routed the present-tense question to
    the future key -- a wrong answer to a legally significant question.
    """
    from jobbot.forms.model import FieldKind, FormField
    from jobbot.healer.answer import classify

    now = FormField("a", "Do you require visa sponsorship?", FieldKind.COMBOBOX)
    future = FormField("b", "Will you now or will you in the future require employment "
                            "visa sponsorship to work in the country in which the job "
                            "you're applying for is located?", FieldKind.COMBOBOX)
    classify(now); classify(future)
    assert now.profile_key == "requires_sponsorship_now"
    assert future.profile_key == "requires_sponsorship_future"
    assert now.legally_significant and future.legally_significant
