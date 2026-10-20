"""Where a repository's documentation is: the organization's convention, or what docs.toml overrides."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from documentation.report import Report

CONFIGURATION = "docs.toml"


class Layout(BaseModel):
    """The settings docs.toml may override; a format we define, so an unknown setting is an error."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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
        return Layout.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except tomllib.TOMLDecodeError as problem:
        report.error(f"{CONFIGURATION}: {problem}")
    except ValidationError as problems:
        for details in problems.errors():
            where = ".".join(map(str, details["loc"]))
            if details["type"] == "extra_forbidden":
                known = ", ".join(Layout.model_fields)
                report.error(f"{CONFIGURATION}: unknown setting '{where}'; known: {known}")
            else:
                report.error(f"{CONFIGURATION}: {where}: {details['msg']}")
    return Layout()
