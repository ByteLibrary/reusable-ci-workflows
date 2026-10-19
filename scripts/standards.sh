#!/usr/bin/env bash
# The ways-of-working rules of the handbook that a machine can check. The pull request
# standards workflow and the git hooks on developer machines both call this script (ADR-0024).
#
# Usage:
#   standards.sh title <title>          a pull request title or a commit subject
#   standards.sh commit-message <file>  a commit message, as git passes it to the commit-msg hook
#   standards.sh branch <name>          a branch name
#   standards.sh description            a pull request description, read from standard input
#   standards.sh attribution <what>     text read from standard input, described as <what>
#   standards.sh names <what>           text read from standard input, described as <what>
#
# Prints what is wrong and exits with 1 when a rule is broken.
set -euo pipefail

types='feat|fix|refactor|perf|test|docs|build|ci|chore'

# Names of AI agents, assistants and vendors that must not appear in our content
# (handbook, ADR-0017). This list is the only place where they are written down.
names_pattern='\b(claude|anthropic|openai|chatgpt|codex|copilot|gemini|windsurf)\b'

attribution_pattern='^co-authored-by:|^(🤖 )?generated (with|by) '

broken=0

report() {
  if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
    echo "::error::$*"
  else
    echo "error: $*" >&2
  fi
  broken=1
}

check_title() {
  local pattern="^($types)(\([a-z0-9-]+\))?!?: [a-z0-9\`].*[^.]$"
  if [[ ! "$1" =~ $pattern ]]; then
    report "'$1' is not a Conventional Commit: '<type>(<scope>): <description>', lowercase, imperative, without a trailing period."
  fi
}

check_attribution() {
  local matches
  matches="$(grep -inE "$attribution_pattern" <<<"$2" || true)"
  if [[ -n "$matches" ]]; then
    report "$1 contains co-author trailers or tool attribution:"
    head -5 <<<"$matches" >&2
  fi
}

check_names() {
  local matches
  matches="$(grep -inE "$names_pattern" <<<"$2" || true)"
  if [[ -n "$matches" ]]; then
    report "$1 names a specific agent tool or vendor:"
    head -5 <<<"$matches" >&2
  fi
}

check_commit_message() {
  local message subject
  # git ignores comment lines and everything below the scissors line of a verbose commit.
  message="$(sed '/^# -\{24\} >8 -\{24\}$/,$d' "$1" | grep -v '^#' || true)"
  subject="$(grep -m1 -v '^[[:space:]]*$' <<<"$message" || true)"
  # Fixup commits are squashed away before the branch is merged.
  if [[ ! "$subject" =~ ^(fixup|squash|amend)!\  ]]; then
    check_title "$subject"
  fi
  check_attribution "The commit message" "$message"
  check_names "The commit message" "$message"
}

check_branch() {
  local pattern="^($types)/[0-9]+-[a-z0-9]+(-[a-z0-9]+)*$"
  if [[ ! "$1" =~ $pattern ]]; then
    report "'$1' is not a branch name of the form '<type>/<issue-number>-<short-description>', in lowercase kebab-case."
  fi
  check_names "The branch name" "$1"
}

check_description() {
  local body
  body="$(tr -d '\r')"
  grep -qiE '^closes (ByteLibrary/[A-Za-z0-9._-]+)?#[0-9]+' <<<"$body" ||
    report "The description is missing a line 'Closes #<issue>'."
  local heading
  for heading in "## Why" "## What changed" "## How it was verified"; do
    grep -qxF "$heading" <<<"$body" || report "The description is missing the heading '$heading'."
  done
}

usage() {
  sed -n '6,12p' "$0" >&2
  exit 2
}

command="${1:-}"
case "$command" in
  title) (($# == 2)) || usage; check_title "$2" ;;
  commit-message) (($# == 2)) || usage; check_commit_message "$2" ;;
  branch) (($# == 2)) || usage; check_branch "$2" ;;
  description) (($# == 1)) || usage; check_description ;;
  attribution) (($# == 2)) || usage; check_attribution "$2" "$(cat)" ;;
  names) (($# == 2)) || usage; check_names "$2" "$(cat)" ;;
  *) usage ;;
esac

exit "$broken"
