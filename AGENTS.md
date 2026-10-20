# Agent guide: reusable-ci-workflows

Reusable GitHub Actions workflows called by every repository. Organization rules are in the
handbook (`handbook/AGENTS.md`); its strict rules apply here.

- A change here affects every repository. Keep checks strict about the handbook's rules and silent
  about everything else.
- Pass untrusted values (titles, descriptions, branch names) to scripts only through `env`, never by
  writing `${{ }}` expressions inside `run`.
- Pin actions to a full commit SHA with the version in a comment.
- `scripts/standards.py` holds the rules that git hooks and CI share (ADR-0024), including the only
  list of banned agent tool and vendor names (ADR-0017). Do not copy them anywhere else.
- Before opening a pull request, test each changed check with a case that must pass and one that must
  fail; describe them under "How it was verified".
