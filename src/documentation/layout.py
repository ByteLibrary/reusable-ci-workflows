"""Where a repository's documentation is: the organization's convention, or what docs.toml overrides."""

from dataclasses import dataclass, fields
from pathlib import Path

import tomllib

from documentation.report import Report

CONFIGURATION = "docs.toml"


@dataclass
class Layout:
    # The folder of documents with frontmatter.
    documents: str = "docs"
    # The folder of decisions (ADRs), named NNNN-short-title.md.
    decisions: str = "docs/adr"
    # Documents grouped in numbered section folders at the root (00-overview/…), as in the handbook,
    # instead of one documents folder.
    sections: bool = False
    # List READMEs next to parts of the code, outside the documents.
    part_readmes: bool = True
    # A Python file with the repository's own views and checks, relative to the root.
    extension: str | None = None


def load(root: Path, report: Report) -> Layout:
    """The convention, with whatever docs.toml at the root overrides."""
    path = root / CONFIGURATION
    if not path.exists():
        return Layout()
    try:
        settings = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as problem:
        report.error(f"{CONFIGURATION}: {problem}")
        return Layout()
    known = {field.name: field.type for field in fields(Layout)}
    for key in sorted(settings.keys() - known.keys()):
        report.error(f"{CONFIGURATION}: unknown setting '{key}'; known: {', '.join(known)}")
    return Layout(**{key: value for key, value in settings.items() if key in known})
