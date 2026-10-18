#!/usr/bin/env bash
# Tests standards.sh: every rule with a case that must pass and one that must fail.
set -euo pipefail

standards="$(dirname "$0")/standards.sh"
# A banned name, read from the script so the list stays in one place.
banned="$(sed -n "s/^names_pattern='\\\\b(\([a-z]*\)|.*/\1/p" "$standards")"
[[ -n "$banned" ]] || { echo "could not read a banned name from standards.sh" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=0

expect() {
  local outcome="$1" description="$2"
  shift 2
  if "$@" >/dev/null 2>&1; then actual=pass; else actual=fail; fi
  if [[ "$actual" == "$outcome" ]]; then
    echo "ok   $description"
  else
    echo "FAIL $description: expected $outcome, got $actual"
    failures=$((failures + 1))
  fi
}

with_input() {
  local input="$1"
  shift
  "$@" <<<"$input"
}

message() {
  printf '%s\n' "$@" >"$work/message"
  echo "$work/message"
}

expect pass "title: conventional" "$standards" title "feat(catalog): add work relations"
expect pass "title: breaking change" "$standards" title "feat!: drop the old api"
expect fail "title: unknown type" "$standards" title "feature: add work relations"
expect fail "title: capital letter" "$standards" title "feat: Add work relations"
expect fail "title: trailing period" "$standards" title "feat: add work relations."

expect pass "commit message: conventional, with body" "$standards" commit-message "$(message "fix: ignore stale positions" "" "Positions older than the stored one are dropped.")"
expect pass "commit message: comment lines are ignored" "$standards" commit-message "$(message "docs: fix a typo" "# Please enter the commit message")"
expect pass "commit message: text below the scissors line is ignored" "$standards" commit-message "$(message "docs: fix a typo" "# ------------------------ >8 ------------------------" "Co-authored-by: someone")"
expect pass "commit message: fixup commit" "$standards" commit-message "$(message "fixup! docs: fix a typo")"
expect fail "commit message: not conventional" "$standards" commit-message "$(message "Fix typo")"
expect fail "commit message: co-author trailer" "$standards" commit-message "$(message "docs: fix a typo" "" "Co-authored-by: someone <someone@example.com>")"
expect fail "commit message: attribution" "$standards" commit-message "$(message "docs: fix a typo" "" "Generated with some tool")"
expect fail "commit message: banned name" "$standards" commit-message "$(message "docs: thank $banned")"

expect pass "branch: conventional" "$standards" branch "feat/12-work-relations"
expect fail "branch: no issue number" "$standards" branch "feat/work-relations"
expect fail "branch: unknown type" "$standards" branch "feature/12-work-relations"
expect fail "branch: capital letters" "$standards" branch "feat/12-Work-Relations"
expect fail "branch: banned name" "$standards" branch "feat/12-$banned-setup"

complete=$'Closes #3\n\n## Why\nBecause.\n\n## What changed\nThis.\n\n## How it was verified\nTests.'
expect pass "description: complete" with_input "$complete" "$standards" description
expect pass "description: closes an issue in another repository" with_input "${complete/Closes #3/Closes ByteLibrary/roadmap#26}" "$standards" description
expect fail "description: no issue" with_input "${complete/Closes #3/}" "$standards" description
expect fail "description: missing heading" with_input "$(sed '/^## Why$/d' <<<"$complete")" "$standards" description

expect pass "attribution: none" with_input "plain text" "$standards" attribution "The text"
expect fail "attribution: co-author trailer" with_input "Co-Authored-By: someone" "$standards" attribution "The text"
expect pass "names: none" with_input "an agent tool" "$standards" names "The text"
expect fail "names: banned name, any case" with_input "Thanks ${banned^^}" "$standards" names "The text"

expect fail "usage: unknown command" "$standards" unknown

if ((failures > 0)); then
  echo "$failures test(s) failed"
  exit 1
fi
echo "all tests passed"
