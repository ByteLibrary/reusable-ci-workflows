# reusable-ci-workflows

Reusable GitHub Actions workflows that check every ByteLibrary repository. Each check enforces a rule
from the organization handbook, so mistakes are caught before merging, for humans and agents alike.

| Workflow | Job | Checks |
|---|---|---|
| `pull-request-standards.yml` | Pull request standards | Title is a Conventional Commit; description has `Closes`, Why, What changed, How it was verified; commits have no co-author trailers or attribution; no agent tool or vendor names in the title, description, branch, commits or added lines |
| `documentation.yml` | Documentation links | Relative Markdown links, frontmatter `related` references and `llms.txt` entries resolve |
| `shell.yml` | Shell scripts | Every shell script parses, and `shellcheck` reports no warnings or errors |

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
runs in this repository's CI.

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
  pull-request-standards:
    uses: ByteLibrary/reusable-ci-workflows/.github/workflows/pull-request-standards.yml@main
  documentation:
    uses: ByteLibrary/reusable-ci-workflows/.github/workflows/documentation.yml@main
  shell:
    uses: ByteLibrary/reusable-ci-workflows/.github/workflows/shell.yml@main
```

`edited` makes the checks run again when a pull request's title or description changes. This
repository's Actions access is set to the organization, which lets private ByteLibrary repositories
call these workflows.

## Changing a workflow
- Workflows take no inputs and need no secrets. Untrusted values (titles, descriptions, branch names)
  reach scripts only through environment variables.
- Actions are pinned to a full commit SHA, with the version in a comment.
- A new check must catch a real mistake; see the testing convention in the handbook.
- This repository's own CI runs the workflows from the pull request branch, so a change is tested by
  its own pull request.
