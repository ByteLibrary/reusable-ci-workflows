# reusable-ci-workflows

Reusable GitHub Actions workflows that check every repository. Each check enforces a rule from the
handbook, so mistakes are caught before merging, for humans and agents alike.

| Workflow | Check | Checks |
|---|---|---|
| `compliance.yml` | Shared / Compliance | The handbook's rules that apply regardless of language, one step each: the title is a Conventional Commit; the description has `Closes`, Why, What changed, How it was verified; commits have no co-author trailers or attribution; no agent tool or vendor names in the title, description, branch, commits or added lines; relative Markdown links, frontmatter `related` references and `llms.txt` entries resolve |
| `lint.yml` | Shared / Lint | `scripts/lint.py`: every language the repository uses, its documentation, then the repository's own `mise run lint` |

## The rules script
`scripts/standards.py` holds the handbook's rules that a machine can check: Conventional Commit titles
and commit messages, branch names, the pull request description, no co-author trailers or attribution,
and no agent tool or vendor names. `compliance.yml` calls it in CI, and the git hooks on
developer machines call it from the workspace clone of this repository, so both apply the same rules.
It needs only Python's standard library, so it runs before any tool is installed.

```bash
scripts/standards.py title "feat(catalog): add work relations"
scripts/standards.py branch feat/12-work-relations
scripts/standards.py commit-message .git/COMMIT_EDITMSG
```

`tests/test_standards.py` tests every rule with a case that must pass and one that must fail, and
`tests/test_lint.py` does the same for the lint script. `mise run test` runs both, as this
repository's `Tests` check does.

## The lint script
`scripts/lint.py` lints a repository with the organization's settings and the tool versions pinned
in `mise.toml`:

| Language | Files | Tool |
|---|---|---|
| Shell | `.sh` files, and files without an extension whose first line is a shell shebang | `bash -n` and `shellcheck` |
| Python | `.py` files | `ruff format --check` and `ruff check`, with `ruff.toml` |
| Go | a `go.mod` at the root | `golangci-lint run` with `.golangci.yml` (lint, and gofmt and goimports formatting), using the Go version the repository pins |

Each language the repository uses, Python or Go, must be pinned under `[tools]` in its own
`mise.toml`, so it never runs on whatever version a machine has; the script names any missing pin.
It then runs the repository's own `mise run lint`, if the repository defines one, for checks specific
to it. Files marked `linguist-generated` or `linguist-vendored` in `.gitattributes` are skipped.
`lint.yml` runs it in CI, and it runs the same way locally from the workspace clone:

```bash
~/ByteLibrary/reusable-ci-workflows/scripts/lint.py ~/ByteLibrary/playbook
```

A new language is a new step here, with its settings in this repository.

## The documentation generator
`src/documentation` validates a repository's documentation and generates the views derived from it:
indexes, the index of decisions, and `llms.txt`. `Shared / Lint` checks any repository with a `docs/`
folder, a `docs.toml` or an `llms.txt`; in the workspace, a repository's `mise run docs` regenerates its views.

By default, documents with frontmatter live in `docs/`, decisions in `docs/adr/`, and READMEs next to parts
are listed from their first heading and paragraph. A `docs.toml` at the repository's root changes that
layout, or adds the repository's own views and checks. How it works and how to extend it:
[src/documentation](src/documentation/README.md).

## Using the workflows
A repository calls the workflows that apply to it from `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    types: [opened, edited, reopened, synchronize]

permissions:
  contents: read

jobs:
  compliance:
    name: Shared
    uses: ByteLibrary/reusable-ci-workflows/.github/workflows/compliance.yml@main
  lint:
    name: Shared
    uses: ByteLibrary/reusable-ci-workflows/.github/workflows/lint.yml@main
```

The calling jobs are named `Shared`, so the checks read `Shared / Compliance` and `Shared / Lint`.

`edited` makes the checks run again when a pull request's title or description changes. This
repository's Actions access is set to the organization, which lets the private repositories
call these workflows.

## Changing a workflow
- Workflows take no inputs and need no secrets. Untrusted values (titles, descriptions, branch names)
  reach scripts only through environment variables.
- Actions are pinned to a full commit SHA, with the version in a comment.
- A new check must catch a real mistake; see the testing convention in the handbook.
- This repository's own CI runs the workflows from the pull request branch, so a change is tested by
  its own pull request.
