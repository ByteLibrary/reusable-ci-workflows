#!/usr/bin/env bash
# Tests lint.sh on throwaway repositories: each language with a case that must pass and one that must
# fail, scripts found by their shebang, skipped files, and a repository's own lint task.
set -euo pipefail

lint="$(cd "$(dirname "$0")" && pwd)/lint.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=0

expect() {
  local outcome="$1" description="$2" repository="$3"
  if "$lint" "$repository" >"$work/output" 2>&1; then actual=pass; else actual=fail; fi
  if [[ "$actual" == "$outcome" ]]; then
    echo "ok   $description"
  else
    echo "FAIL $description: expected $outcome, got $actual"
    sed 's/^/     /' "$work/output"
    failures=$((failures + 1))
  fi
}

# A new repository holding the given files, written as "<path>" "<content>" pairs.
repository() {
  local directory="$work/$1"
  shift
  git init --quiet "$directory"
  while (($# > 0)); do
    mkdir -p "$(dirname "$directory/$1")"
    printf '%s\n' "$2" >"$directory/$1"
    shift 2
  done
  git -C "$directory" add --all
  echo "$directory"
}

clean_shell=$'#!/usr/bin/env bash\necho "hello"'
# A variable that is never used is a shellcheck warning (SC2034).
broken_shell=$'#!/usr/bin/env bash\nunused="value"'

expect pass "no code" "$(repository empty README.md "# Empty")"
expect pass "shell: clean script" "$(repository shell-clean run.sh "$clean_shell")"
expect fail "shell: warning" "$(repository shell-broken run.sh "$broken_shell")"
expect fail "shell: script without an extension, found by its shebang" "$(repository hook hooks/pre-push "$broken_shell")"
expect pass "shell: file without an extension and without a shebang is not a script" "$(repository plain hooks/notes "unused=value")"
expect pass "shell: generated file is skipped" "$(repository generated gen/run.sh "$broken_shell" .gitattributes "gen/** linguist-generated")"
expect pass "shell: vendored file is skipped" "$(repository vendored vendor/run.sh "$broken_shell" .gitattributes "vendor/** linguist-vendored")"

expect pass "python: clean file" "$(repository python-clean app.py 'print("hello")')"
expect fail "python: not formatted" "$(repository python-format app.py "print( 'hello' )")"
expect fail "python: lint error" "$(repository python-lint app.py $'import os\n\nprint("hello")')"

documented() {
  local directory
  directory="$(repository "$1" README.md $'# Example\n\nWhat it is for.' docs/guide.md "$2")"
  # The generated llms.txt, as `mise run docs` would write it.
  (cd "$(dirname "$lint")/.." && mise exec -- uv run --quiet --frozen documentation generate --quiet --root "$directory") >/dev/null 2>&1 || true
  echo "$directory"
}
expect pass "documentation: documents with frontmatter" "$(documented docs-good $'---\ntitle: Guide\nsummary: How to use it\norder: 1\nstatus: active\nrelated: []\n---\n\n# Guide')"
expect fail "documentation: a document without frontmatter" "$(documented docs-bad $'# Guide')"

own_task() {
  local directory
  directory="$(repository "$1" mise.toml "$(printf '[tasks.lint]\nrun = "%s"' "$2")")"
  mise trust --quiet "$directory/mise.toml"
  echo "$directory"
}
expect pass "own lint task: passes" "$(own_task own-pass true)"
expect fail "own lint task: fails" "$(own_task own-fail false)"

if ((failures > 0)); then
  echo "$failures test(s) failed"
  exit 1
fi
echo "all tests passed"
