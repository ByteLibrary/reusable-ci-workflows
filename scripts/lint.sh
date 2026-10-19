#!/usr/bin/env bash
# Lints a repository: every language it uses, with the organization's settings and the tool versions
# pinned in this repository's mise.toml, its documentation, if it has a docs/ folder, a docs.toml or an
# llms.txt, and then the repository's own `mise run lint`, if it has one.
# The Lint check in CI and developers run this same script.
#
# Usage: lint.sh [<repository>]   the repository's folder, by default the current one
#
# Files marked linguist-generated or linguist-vendored in .gitattributes are skipped. Prints what is
# wrong and exits with 1 when a linter finds a problem.
set -euo pipefail

rules_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "${1:-.}"
repository_dir="$(pwd)"

# Runs a tool at the version pinned in this repository, on files given relative to the repository.
pinned() {
  (cd "$rules_dir" && mise exec -- "$@")
}

# Tracked files, without generated or vendored ones. check-attr prints "<file>: <attribute>: <value>".
mapfile -t files < <(
  git ls-files -z | git check-attr --stdin -z linguist-generated linguist-vendored |
    paste -z -d '\t\t' - - - | tr '\0' '\n' |
    awk -F '\t' '{ skip[$1] = skip[$1] || ($3 == "set" || $3 == "true") } END { for (f in skip) if (!skip[f]) print f }' |
    sort
)

shell_scripts=()
python_files=()
for file in "${files[@]}"; do
  [[ -f "$file" ]] || continue
  case "${file##*/}" in
    *.sh) shell_scripts+=("$repository_dir/$file") ;;
    *.py) python_files+=("$repository_dir/$file") ;;
    *.*) ;;
    *)
      # Scripts without an extension, such as git hooks, are recognized by their shebang.
      if head -n 1 "$file" | grep -qE '^#!.*\b(ba)?sh\b'; then
        shell_scripts+=("$repository_dir/$file")
      fi
      ;;
  esac
done

failed=0

if ((${#shell_scripts[@]} > 0)); then
  echo "Shell: ${#shell_scripts[@]} script(s)"
  for script in "${shell_scripts[@]}"; do
    bash -n "$script" || failed=1
  done
  pinned shellcheck --severity=warning --external-sources "${shell_scripts[@]}" || failed=1
fi

if ((${#python_files[@]} > 0)); then
  echo "Python: ${#python_files[@]} file(s)"
  pinned ruff format --check --config "$rules_dir/ruff.toml" "${python_files[@]}" || failed=1
  pinned ruff check --config "$rules_dir/ruff.toml" "${python_files[@]}" || failed=1
fi

if [[ -f go.mod ]]; then
  echo "Go"
  # golangci-lint is pinned here, but analyzes the code with the Go version the repository pins, so it
  # runs in the repository, with the repository's tools.
  golangci_lint="$(cd "$rules_dir" && mise which golangci-lint)"
  mise exec -- "$golangci_lint" run --config "$rules_dir/.golangci.yml" ./... || failed=1
fi

if [[ -d docs || -f docs.toml || -f llms.txt ]]; then
  echo "Documentation"
  pinned uv run --quiet --frozen documentation check --quiet --root "$repository_dir" || failed=1
fi

if [[ -f mise.toml ]] && mise tasks info lint >/dev/null 2>&1; then
  echo "This repository's own lint task"
  mise run lint || failed=1
fi

exit "$failed"
