"""The editor's one load-bearing distinction: `false` is not `unset`.

"No" is an answer. "Not set" is the absence of one, and it has to stay absent
through the whole round trip, because an absent key is what makes the run stop
and ask instead of submitting. If these two ever collapse into each other the
failure is silent and lands on a real application, so they get a test.
"""

from __future__ import annotations

import yaml

from jobbot.editor import from_form, save, to_form, validate
from jobbot.profile import Profile

BASE = {
    "identity": {"first_name": "A", "last_name": "B", "email": "a@b.com",
                 "location": {"city": "SF", "state": "CA"}},
    "experience": [], "education": [], "projects": [], "skills": [], "extra": [],
    "compensation": {}, "awards": [], "publications": [],
    "certifications": [], "languages": [],
}


def test_false_is_kept_and_unset_is_dropped() -> None:
    payload = {**BASE, "screening": {
        "criminal_history": False,        # answered: no
        "work_authorization": True,       # answered: yes
        "background_check_consent": None,  # not answered
        "citizenship": "",                # not answered
    }}
    scr = from_form(payload)["screening"]
    assert scr["criminal_history"] is False, "an explicit No must be preserved"
    assert scr["work_authorization"] is True
    assert "background_check_consent" not in scr, "unset must not be written"
    assert "citizenship" not in scr, "an empty string is not an answer"


def test_unset_key_blocks_the_run_and_false_does_not() -> None:
    """The whole point: absence halts, `false` proceeds."""
    answered = Profile.model_validate(from_form({**BASE, "screening": {
        k: False for k in
        ("work_authorization", "requires_sponsorship_now",
         "requires_sponsorship_future", "criminal_history",
         "background_check_consent", "veteran_status", "disability_status",
         "age_over_18", "education_degree", "previously_employed_here")}}))
    assert answered.missing_legally_significant() == [], \
        "every core question answered false is still fully answered"

    partial = Profile.model_validate(from_form({**BASE, "screening": {
        "criminal_history": False, "background_check_consent": None}}))
    assert "background_check_consent" in partial.missing_legally_significant()
    assert "criminal_history" not in partial.missing_legally_significant()


def test_round_trip_through_disk_preserves_false(tmp_path) -> None:
    path = tmp_path / "profile.yaml"
    res = save(path, from_form({**BASE, "screening": {"criminal_history": False}}))
    assert res["ok"], res
    back = to_form(yaml.safe_load(path.read_text()))
    assert back["screening"]["criminal_history"] is False, \
        "a No must survive save/load, not come back as unset"


def test_invalid_payload_leaves_the_file_untouched(tmp_path) -> None:
    path = tmp_path / "profile.yaml"
    save(path, from_form({**BASE, "screening": {}}))
    before = path.read_bytes()

    bad = {**BASE, "identity": {**BASE["identity"], "email": "not-an-email"}}
    res = save(path, from_form(bad))
    assert not res["ok"] and res["errors"]
    assert path.read_bytes() == before, "a rejected submit must not write"


def test_overwrite_keeps_a_backup(tmp_path) -> None:
    path = tmp_path / "profile.yaml"
    save(path, from_form(BASE))
    res = save(path, from_form({**BASE, "headline": "changed"}))
    assert res["backup"], "the previous answer set must be recoverable"
    old = yaml.safe_load(open(res["backup"]).read())
    assert old["headline"] == ""


def test_scalar_and_dict_screening_both_load(tmp_path) -> None:
    """On-disk screening may be a bare scalar or a {value, provenance} dict."""
    raw = yaml.safe_load("""
identity: {first_name: A, last_name: B, email: a@b.com}
screening:
  criminal_history: false
  work_authorization: {value: true, provenance: confirmed}
""")
    flat = to_form(raw)["screening"]
    assert flat["criminal_history"] is False
    assert flat["work_authorization"] is True
    prof, errs = validate(raw)
    assert prof is not None and not errs
    assert prof.can_answer("work_authorization")


def test_a_project_with_only_a_repo_still_gets_a_link() -> None:
    """The resume renders `url`; repo-only projects printed with no link."""
    out = from_form({**BASE, "projects": [
        {"name": "wirefmt", "repo": "github.com/me/wirefmt"},
    ]})
    assert out["projects"][0]["url"] == "https://github.com/me/wirefmt"


def test_bare_domains_get_a_scheme() -> None:
    """People dictate "github.com/me" -- a form field needs the scheme."""
    out = from_form({**BASE, "identity": {
        **BASE["identity"], "github": "github.com/me",
        "linkedin": "https://linkedin.com/in/me",
    }})
    assert out["identity"]["github"] == "https://github.com/me"
    assert out["identity"]["linkedin"] == "https://linkedin.com/in/me"
