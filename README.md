# reusable-ci-workflows

Reusable GitHub Actions workflows that check every repository. Each check enforces a rule from the
handbook, so mistakes are caught before merging, for humans and agents alike.

| Workflow | Check | Checks |
|---|---|---|
| `compliance.yml` | Shared / Compliance | The handbook's rules that apply regardless of language, one step each: the title is a Conventional Commit; the description has `Closes`, Why, What changed, How it was verified; commits have no co-author trailers or attribution; no agent tool or vendor names in the title, description, branch, commits or added lines; relative Markdown links, frontmatter `related` references and `llms.txt` entries resolve |
| `lint.yml` | Shared / Lint | `scripts/lint.sh`: every language the repository uses, then the repository's own `mise run lint` |

`pull-request-standards.yml`, `documentation.yml` and `shell.yml` remain only until every repository
calls `compliance.yml` and `lint.yml`.

## The rules script
`scripts/standards.sh` holds the handbook's rules that a machine can check: Conventional Commit titles
and commit messages, branch names, the pull request description, no co-author trailers or attribution,
and no agent tool or vendor names. `pull-request-standards.yml` calls it in CI, and the git hooks on
developer machines call it from the workspace clone of this repository, so both apply the same rules.

```bash
scripts/standards.sh title "feat(catalog): add work relations"
scripts/standards.sh branch feat/12-work-relations
scripts/standards.sh commit-message .git/COMMIT_EDITMSG
```

`scripts/test-standards.sh` tests every rule with a case that must pass and one that must fail, and
`scripts/test-lint.sh` does the same for the lint script. `mise run test` runs both, as this
repository's `Tests` check does.

## The lint script
`scripts/lint.sh` lints a repository with the organization's settings and the tool versions pinned
in `mise.toml`:

| Language | Files | Tool |
|---|---|---|
| Shell | `.sh` files, and files without an extension whose first line is a shell shebang | `bash -n` and `shellcheck` |
| Python | `.py` files | `ruff format --check` and `ruff check`, with `ruff.toml` |

It then runs the repository's own `mise run lint`, if the repository defines one, for checks specific
to it. Files marked `linguist-generated` or `linguist-vendored` in `.gitattributes` are skipped.
`lint.yml` runs it in CI, and it runs the same way locally from the workspace clone:

```bash
~/ByteLibrary/reusable-ci-workflows/scripts/lint.sh ~/ByteLibrary/playbook
```

A new language is a new step here, with its settings in this repository.

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
