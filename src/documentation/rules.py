"""The rules every repository's documentation follows: frontmatter, statuses, order, sections and
decisions."""

import json
import re
from importlib import resources
from pathlib import Path, PurePosixPath

import jsonschema

from documentation.documents import SECTION, Document, Found
from documentation.layout import Layout
from documentation.report import Report
from documentation.statuses import Kind, Status, allowed, find


def schema(kind: str) -> jsonschema.Draft202012Validator:
    text = (
        resources.files("documentation")
        .joinpath("schemas", f"{kind}.schema.json")
        .read_text(encoding="utf-8")
    )
    return jsonschema.Draft202012Validator(json.loads(text), format_checker=jsonschema.FormatChecker())


def check_frontmatter(found: Found, report: Report) -> None:
    for kind, items in (("document", found.documents), ("decision", found.decisions)):
        validator = schema(kind)
        for item in items:
            meta = {key: value for key, value in item.items() if key not in ("path", "number")}
            for problem in validator.iter_errors(meta):
                report.error(
                    f"{item['path']}: frontmatter {'/'.join(map(str, problem.path))}: {problem.message}"
                )


def check_statuses(found: Found, statuses: list[Status], report: Report) -> None:
    """Every status is one the handbook defines for its kind."""
    kinds: tuple[tuple[Kind, list[Document]], ...] = (
        ("document", found.documents),
        ("decision", found.decisions),
    )
    for kind, items in kinds:
        for item in items:
            status = str(item.get("status", ""))
            if find(statuses, kind, status) is None:
                report.error(
                    f"{item['path']}: status '{status}' is not one the handbook defines for a {kind}: "
                    f"{allowed(statuses, kind)}"
                )


def check_order(found: Found, report: Report) -> None:
    """No two documents in a folder share a reading order."""
    used: dict[tuple[str, int | None], str] = {}
    for document in found.documents:
        key = (str(PurePosixPath(document["path"]).parent), document.get("order"))
        if key in used:
            report.error(f"{document['path']}: order {key[1]} is also used by {used[key]}")
        used[key] = document["path"]


def check_sections(root: Path, report: Report) -> None:
    for section in sections(root):
        if not (root / section / "README.md").exists():
            report.error(f"{section}/: every section needs a README.md")


def check_decisions(found: Found, layout: Layout, report: Report) -> None:
    numbers = sorted(int(decision["number"]) for decision in found.decisions)
    if numbers != list(range(1, len(numbers) + 1)):
        report.error(f"{layout.decisions}/: ADR numbers must run from 0001 without gaps or duplicates")
    for decision in found.decisions:
        if not str(decision.get("title", "")).startswith(f"ADR-{decision['number']}: "):
            report.error(f"{decision['path']}: title must start with 'ADR-{decision['number']}: '")
        superseded = re.match(r"superseded by ADR-(\d{4})$", str(decision.get("status", "")))
        if superseded and int(superseded.group(1)) not in numbers:
            report.error(f"{decision['path']}: superseded by an ADR that does not exist")


def sections(root: Path) -> list[str]:
    """The numbered section folders at the root, for the sections layout."""
    return sorted(path.name for path in root.iterdir() if path.is_dir() and SECTION.match(f"{path.name}/"))


def check(root: Path, layout: Layout, found: Found, statuses: list[Status], report: Report) -> None:
    check_frontmatter(found, report)
    if report.errors:
        return
    check_statuses(found, statuses, report)
    check_order(found, report)
    check_decisions(found, layout, report)
    if layout.sections:
        check_sections(root, report)
