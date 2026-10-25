"""The statuses a document or decision may have, read from the handbook, which defines them."""

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from documentation.layout import Layout
from documentation.report import Report

# The handbook's table of statuses, relative to its root.
TABLE = "data/document-statuses.yaml"
# Where the handbook is, overriding docs.toml; CI sets it to the handbook it checked out.
HANDBOOK = "DOCUMENTATION_HANDBOOK"
# How a decision writes the status `superseded`.
SUPERSEDED = re.compile(r"^superseded by ADR-\d{4}$")

Kind = Literal["document", "decision"]


class Status(BaseModel):
    """A row of the handbook's table; a format we define, so an unknown field is an error."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    applies_to: list[Kind]
    meaning: str
    # Shown at the top of every document or decision with this status.
    notice: str | None = None


STATUSES = TypeAdapter(list[Status])


def handbook(root: Path, layout: Layout) -> Path:
    return Path(os.environ.get(HANDBOOK) or root / layout.handbook).resolve()


def load(root: Path, layout: Layout, report: Report) -> list[Status]:
    path = handbook(root, layout) / TABLE
    if not path.exists():
        report.error(
            f"the handbook's statuses are missing ({path}): clone the handbook next to this repository, "
            f"or point to it with `handbook` in docs.toml or {HANDBOOK}"
        )
        return []
    try:
        return STATUSES.validate_python(yaml.safe_load(path.read_text(encoding="utf-8")))
    except ValidationError as problems:
        for details in problems.errors():
            report.error(f"{path}: {'.'.join(map(str, details['loc']))}: {details['msg']}")
        return []


def find(statuses: list[Status], kind: Kind, status: str) -> Status | None:
    """The table's row for a status as frontmatter writes it, if the kind may have it."""
    code = "superseded" if kind == "decision" and SUPERSEDED.match(status) else status
    return next((row for row in statuses if row.code == code and kind in row.applies_to), None)


def allowed(statuses: list[Status], kind: Kind) -> str:
    """The statuses a kind may have, as frontmatter writes them."""
    return ", ".join(
        "superseded by ADR-NNNN" if kind == "decision" and row.code == "superseded" else row.code
        for row in statuses
        if kind in row.applies_to
    )
