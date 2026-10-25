# The documentation generator

Validates a repository's documentation and generates the views derived from it.

How to run it is in its help, `uv run documentation --help`; this page is for changing it.

## How the parts connect
The command reads the layout, finds every document, reads the statuses from the handbook, loads the
repository's extension if it has one, checks the rules, then renders every generated view, the notices of
the statuses that have one, and `llms.txt`.

```mermaid
flowchart LR
  cli["cli.py<br/>generate or check"] --> layout["layout.py<br/>convention or docs.toml"]
  cli --> documents["documents.py<br/>documents, decisions, parts"]
  cli --> statuses["statuses.py<br/>the handbook's statuses"]
  cli --> extension["extension.py<br/>the repository's views and checks"]
  cli --> rules["rules.py<br/>frontmatter, statuses, order, decisions"]
  cli --> generate["generate.py<br/>markers, notices and llms.txt"]
  generate --> views["views.py<br/>index, sections, adr-index, parts, notice"]
  extension --> views
```

| Module | Does |
|---|---|
| `cli.py` | The command line, and the order: layout, documents, extension, rules, rendering |
| `layout.py` | Where documentation is: the convention, or what `docs.toml` overrides |
| `documents.py` | Finding documents, decisions and part READMEs, and reading their frontmatter or heading |
| `statuses.py` | The statuses documents and decisions may have, and their notices, read from the handbook's `data/document-statuses.yaml`: from the `handbook` folder in `docs.toml` (by default `../handbook`, its workspace clone), or from `DOCUMENTATION_HANDBOOK`, which the Lint check sets to the handbook it checks out |
| `rules.py` | The rules: frontmatter against `schemas/`, statuses against the handbook's, reading order, section READMEs, decision numbers |
| `generate.py` | Rendering the views between markers, the notice under the first heading of every document whose status has one, and `llms.txt` |
| `views.py` | The views every repository can use, and helpers for a repository's own views |
| `extension.py` | Loading a repository's own views and checks from the file `docs.toml` names |
| `report.py` | The problems found, reported together at the end |

## Extending it
- **A view or rule for every repository:** add it to `views.py` or `rules.py`, with a test in `tests/`.
- **A view or rule for one repository:** put it in that repository's extension, named in its `docs.toml`
  (`extension = "scripts/docs_views.py"`). The file may define `VIEWS`, `load(root, error)` and
  `validate(context, error)`; see `extension.py`. A view receives its marker's argument as `folder`,
  plus `root`, `documents`, `decisions`, `readmes` and whatever `load` returns.
