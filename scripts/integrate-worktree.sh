#!/bin/zsh
# Squash-merge one worktree branch into the current integration branch, gated on
# the locked suite. Refuses to leave a broken tree behind: on any failure it
# resets back to the pre-merge commit.
#
#   scripts/integrate-worktree.sh work/intake "intake: collage redesign"
#
# Blast radius: only the integration branch moves. The worktree branch is left
# untouched so a failed merge can be retried after fixes.

set -e
BRANCH="$1"
MSG="$2"
[[ -z "$BRANCH" || -z "$MSG" ]] && { print -u2 "usage: $0 <branch> <message>"; exit 2 }

ROOT=${0:a:h:h}
cd "$ROOT"

BEFORE=$(git rev-parse HEAD)
INTEG=$(git branch --show-current)
print "integration branch : $INTEG @ ${BEFORE:0:7}"
print "merging            : $BRANCH"

rollback() {
  print -u2 "\n✗ $1 — rolling back to ${BEFORE:0:7}"
  git merge --abort 2>/dev/null || true
  git reset -q --hard "$BEFORE"
  exit 1
}

# 1. squash the branch in without committing, so conflicts surface before history moves
git merge --squash "$BRANCH" >/dev/null 2>&1 || rollback "squash merge hit conflicts"

CHANGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
print "files staged       : $CHANGED"
[[ "$CHANGED" == "0" ]] && { print "nothing to merge"; git reset -q --hard "$BEFORE"; exit 0 }
git diff --cached --name-only | sed 's/^/                     /'

# 2. commit, then gate on the locked suite
git commit -q -m "$MSG"

print "\nrunning locked suite…"
if ! JOBBOT_UNLOCKED_TESTS=1 .venv/bin/pytest tests/locked/ -q 2>&1 | tail -5; then
  rollback "locked tests failed"
fi

# 3. the suite passes with the guard off; now prove the lock manifest is honest
print "\nverifying lock manifest…"
if ! .venv/bin/pytest tests/locked/ -q 2>&1 | tail -3; then
  print -u2 "\n! lock manifest is stale — test files changed without regenerating LOCK.sha256"
  print -u2 "  run: scripts/relock-tests.sh   then re-run this script"
  rollback "lock manifest mismatch"
fi

print "\n✓ merged $BRANCH → $INTEG as $(git rev-parse --short HEAD)"
