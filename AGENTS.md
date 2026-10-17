# Agent guide: reusable-ci-workflows

Reusable GitHub Actions workflows called by every ByteLibrary repository. Organization rules are in the
organization handbook (`handbook/AGENTS.md`); its strict rules apply here.

- A change here affects every repository. Keep checks strict about the handbook's rules and silent
  about everything else.
- Pass untrusted values (titles, descriptions, branch names) to scripts only through `env`, never by
  writing `${{ }}` expressions inside `run`.
- Pin actions to a full commit SHA with the version in a comment.
- `pull-request-standards.yml` holds the only list of banned agent tool and vendor names (ADR-0017).
  Do not copy it anywhere else.
- Before opening a pull request, test each changed check with a case that must pass and one that must
  fail; describe them under "How it was verified".
