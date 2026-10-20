"""Validates a repository's documentation, and generates the views derived from it.

Documents carry frontmatter; views are written between "BEGIN GENERATED <view>" and "END GENERATED"
markers, and llms.txt is generated whole. The layout is the organization's convention, or what the
repository's docs.toml overrides. The rules: 40-conventions/documentation.md in the handbook.

Examples:
  documentation generate                  validate, then rewrite every generated view
  documentation check                     validate, then fail if a generated view is out of date
  documentation check --root ../handbook  check another repository
"""

import argparse
import json
import sys
from pathlib import Path

from documentation import rules
from documentation.documents import discover
from documentation.extension import Context, load_extension
from documentation.generate import generated_files
from documentation.layout import load
from documentation.report import Report
from documentation.views import VIEWS


def build(root: Path, report: Report) -> dict[str, str]:
    """Every generated file's new text, after validating; nothing when validation fails."""
    layout = load(root, report)
    found = discover(root, layout, report)
    extension = load_extension(root, layout, report)
    context: Context = {
        "root": root,
        "documents": found.documents,
        "decisions": found.decisions,
        "readmes": found.readmes,
        **extension.load(root, report.error),
    }
    if report.errors:
        return {}
    rules.check(root, layout, found, report)
    extension.validate(context, report.error)
    if report.errors:
        return {}
    return generated_files(root, layout, found, {**VIEWS, **extension.views}, context, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="documentation",
        description=__doc__.split("\n\n")[0].replace("\n", " "),
        epilog="\n\n".join(__doc__.split("\n\n")[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("action", choices=("generate", "check"), help="rewrite the views, or only check them")
    parser.add_argument("--root", default=".", help="the repository's folder (default: the current folder)")
    parser.add_argument("--json", action="store_true", help="print the result as one JSON document")
    parser.add_argument("--quiet", action="store_true", help="print only errors")
    arguments = parser.parse_args(argv)
    root = Path(arguments.root).resolve()

    report = Report()
    files = build(root, report)
    stale = sorted(
        path
        for path, text in files.items()
        if not (root / path).exists() or (root / path).read_text(encoding="utf-8") != text
    )
    updated = []
    if arguments.action == "generate" and not report.errors:
        for path in stale:
            (root / path).write_text(files[path], encoding="utf-8")
            updated.append(path)
    elif arguments.action == "check":
        for path in stale:
            report.error(f"{path}: generated view is out of date; run `mise run docs`")

    if arguments.json:
        print(json.dumps({"updated": updated, "errors": report.errors}, indent=2))
    else:
        if not arguments.quiet:
            for path in updated:
                print(f"updated {path}")
        for message in report.errors:
            print(f"ERR {message}", file=sys.stderr)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
