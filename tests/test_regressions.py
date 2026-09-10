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


def test_a_live_profile_holder_is_named_a_dead_one_is_cleared(tmp_path) -> None:
    """A run killed mid-flight leaves Chromium holding the persistent profile.

    Every later run then died inside Playwright with "Opening in existing
    browser session" -- no pid, no hint that the profile was the problem, and
    no way to recover but to find the process by hand.
    """
    import os

    from jobbot.browser.session import BrowserConfig, BrowserSession

    prof = tmp_path / "main"
    prof.mkdir()
    sess = BrowserSession(BrowserConfig(profile_dir=prof))

    assert sess._singleton_holder() is None, "no lock file at all is not a holder"

    # a lock naming this very process: genuinely held
    os.symlink(f"somehost-{os.getpid()}", prof / "SingletonLock")
    assert sess._singleton_holder() == os.getpid()

    # a lock naming a pid that cannot exist: stale, and clearable
    (prof / "SingletonLock").unlink()
    os.symlink("somehost-2147483647", prof / "SingletonLock")
    (prof / "SingletonCookie").symlink_to("123")
    assert sess._singleton_holder() is None
    assert sess._clear_stale_lock()
    assert not (prof / "SingletonLock").exists()
    assert not (prof / "SingletonCookie").exists()


def test_the_verifier_is_told_the_pages_own_validity_state() -> None:
    """A colour cannot distinguish "required" from "invalid".

    On Greenhouse a filled, valid, required field carries an accent that reads
    as an error outline in a screenshot. The verifier reported it as a blocker,
    the heal loop could not clear it (nothing was wrong), and the run could
    never reach `prepared`. The DOM reported aria-invalid="false" throughout.
    """
    from jobbot.forms.model import FieldKind, FormField, ParsedForm
    from jobbot.healer.checkpoints import _validity_block

    form = ParsedForm(fields=[
        FormField("a", "Are you open to relocation?", FieldKind.COMBOBOX,
                  required=True, selector="#a"),
        FormField("b", "Email", FieldKind.EMAIL, required=True, selector="#b"),
    ])
    all_valid = _validity_block(form, {
        "a": {"invalid": False, "message": "", "value_len": 2},
        "b": {"invalid": False, "message": "", "value_len": 9},
    })
    assert "All 2 controls report VALID" in all_valid
    assert "coloured border alone is not evidence" in all_valid

    one_bad = _validity_block(form, {
        "a": {"invalid": True, "message": "Please select an item in the list", "value_len": 0},
        "b": {"invalid": False, "message": "", "value_len": 9},
    })
    assert "reporting INVALID" in one_bad
    assert "Are you open to relocation?: Please select an item" in one_bad

    assert _validity_block(form, {}) == "", "no signal, no claim"


def test_a_richer_profile_does_not_score_lower_on_the_same_job() -> None:
    """The skill bar scaled with profile size: 69 skills needed 24 hits.

    A real 69-skill profile scored 0.35-0.40 on every one of 598 postings and
    the run attempted nothing. Same job, same matching skills, fewer listed
    skills -> higher score is the wrong way round.
    """
    from jobbot.ats.detect import ATS
    from jobbot.discovery.sources import JobPost
    from jobbot.orchestrator import fit_score
    from jobbot.profile import Profile

    jd = "We want Python, Go, PostgreSQL, Docker, Kubernetes, Redis, Kafka and Linux."
    post = JobPost(ats=ATS.GREENHOUSE, native_id="1", company="C",
                   title="Software Engineer", url="u", description=jd)
    core = ["Python", "Go", "PostgreSQL", "Docker", "Kubernetes", "Redis", "Kafka", "Linux"]
    lean = Profile.model_validate({"identity": {}, "target_titles": ["Software Engineer"],
                                   "skills": {"Core": core}})
    rich = Profile.model_validate({"identity": {}, "target_titles": ["Software Engineer"],
                                   "skills": {"Core": core, "Also": [f"skill{i}" for i in range(60)]}})
    assert fit_score(rich, post) == fit_score(lean, post), \
        "listing more skills must not lower the score for the same matching set"
    assert fit_score(rich, post) >= 0.9


def test_title_match_survives_word_order_and_a_level_suffix() -> None:
    """"Machine Learning Engineer Intern" describes "Machine Learning
    Infrastructure Engineer"; a substring test said it did not, and every title
    on a 598-posting board scored the no-match floor."""
    from jobbot.orchestrator import _title_match

    targets = ["Machine Learning Engineer Intern", "Software Engineering Intern"]
    assert _title_match(targets, "Machine Learning Infrastructure Engineer")[0] == 1.0
    assert _title_match(targets, "Senior Software Security Engineer")[1] == 1.0, \
        "'engineering' must meet 'engineer'"
    assert _title_match(targets, "Product Support Specialist") == (0.45, 0.0), \
        "no shared word: floor, and flagged as such"
    partial = _title_match(targets, "Research Engineer, Discovery")
    assert 0.45 < partial[0] < 1.0


def test_a_title_sharing_no_word_with_any_target_is_not_a_match() -> None:
    """A description mentioning Python and Linux is not enough on its own."""
    from jobbot.ats.detect import ATS
    from jobbot.discovery.sources import JobPost
    from jobbot.orchestrator import fit_score
    from jobbot.profile import Profile

    prof = Profile.model_validate({"identity": {},
        "target_titles": ["Machine Learning Engineer Intern"],
        "skills": {"x": ["Python", "Linux", "Git", "SQL", "Docker", "Bash", "Jira", "Slack"]}})
    jd = "Python Linux Git SQL Docker Bash Jira Slack -- help customers."
    support = JobPost(ats=ATS.GREENHOUSE, native_id="1", company="C",
                      title="Product Support Specialist", url="u", description=jd)
    ml = JobPost(ats=ATS.GREENHOUSE, native_id="2", company="C",
                 title="Machine Learning Infrastructure Engineer", url="u", description=jd)
    assert fit_score(prof, ml) >= 0.9
    assert fit_score(prof, support) < 0.5, "identical description, unrelated title -> below threshold"


def test_excluded_companies_are_never_queued() -> None:
    """The user had already applied to Palantir by hand; the run picked it as
    its top match anyway. There was no way to say "not this one"."""
    from jobbot.profile import Profile

    p = Profile.model_validate({"identity": {}, "exclude_companies": ["Palantir", "Example Corp"]})
    assert p.excludes("palantir") and p.excludes("Palantir Technologies")
    assert p.excludes("EXAMPLE CORP")
    assert not p.excludes("Nuro") and not p.excludes("")
    assert not Profile.model_validate({"identity": {}}).excludes("Palantir")


def test_a_state_code_matches_the_state_name() -> None:
    """A location dropdown says "Seattle, WA"; the answer says the state in full.

    Those scored below every threshold, so a required location field stayed
    empty through four heal rounds and the application could not be submitted.
    """
    from jobbot.forms.matching import match_option, normalize

    assert match_option("Seattle, Washington, United States",
                        ["Seattle, WA", "Costa Mesa, CA (HQ)"])[0] == "Seattle, WA"
    assert match_option("San Jose, California, United States",
                        ["San Jose, CA", "Austin, TX"])[0] == "San Jose, CA"

    # Only a trailing code expands: these are ordinary words mid-sentence.
    assert "indiana" not in normalize("will you work in office")
    assert "oregon" not in normalize("answer yes or no")
    assert match_option("Yes", ["Yes", "No"])[0] == "Yes"


def test_a_selector_survives_an_id_that_starts_with_a_digit() -> None:
    """CSS.escape belongs in an identifier, not inside a quoted attribute.

    Ashby ids are UUIDs, so about half begin with a digit. Escaping those into
    "#\\32 ba77b0f-..." produced a selector matching nothing, and two required
    fields -- LinkedIn and an essay question -- were silently never filled.
    """
    import re
    from pathlib import Path

    js = Path("jobbot/forms/extract.py").read_text()
    assert 'return `[id="${attrEsc(el.id)}"]`' in js, \
        "the id selector must be an attribute selector, which needs no escaping"
    assert not re.search(r'label\[for="\$\{esc\}"\]', js), \
        "a CSS-escaped id inside a quoted attribute matches nothing"
