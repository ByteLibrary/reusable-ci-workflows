"""Finding a repository's documents, decisions and part READMEs, and reading their frontmatter."""

import datetime
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, TypedDict, cast

import yaml

from documentation.layout import Layout
from documentation.report import Report

# A numbered section folder at the root, such as 00-overview/.
SECTION = re.compile(r"^\d{2}-[^/]+/")


class Document(TypedDict, total=False):
    """A document's or decision's frontmatter, with where it was found. Its fields are what the JSON
    Schemas in schemas/ define, checked by the rules; views and extensions read it as a dict."""

    path: str
    # Decisions only: the NNNN of the file's name.
    number: str
    title: str
    summary: str
    order: int
    status: str
    date: str
    related: list[str]


@dataclass(frozen=True, slots=True)
class PartReadme:
    """A plain README next to a part of the code."""

    path: str
    title: str
    summary: str


@dataclass(frozen=True, slots=True)
class Found:
    documents: list[Document]
    decisions: list[Document]
    readmes: list[PartReadme]


def markdown_files(root: Path) -> list[str]:
    """Every Markdown file git tracks or would track, so ignored ones are left out."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return sorted(path for path in set(listed) if (root / path).exists())


def decision_pattern(layout: Layout) -> re.Pattern[str]:
    """A decision's path: NNNN-short-title.md in the decisions folder."""
    return re.compile(rf"^{re.escape(layout.decisions)}/(\d{{4}})-[a-z0-9-]+\.md$")


def is_document(path: str, layout: Layout) -> bool:
    if layout.sections:
        return bool(SECTION.match(path))
    return path.startswith(f"{layout.documents}/")


def read_frontmatter(root: Path, path: str, report: Report) -> dict[str, Any]:
    """The frontmatter as YAML reads it; the rules check it against its schema afterwards."""
    text = (root / path).read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        report.error(f"{path}: missing frontmatter")
        return {}
    meta = yaml.safe_load(text[4 : text.index("\n---\n", 4)]) or {}
    # YAML reads a date as a date; the schema expects the text.
    return {
        key: value.isoformat() if isinstance(value, datetime.date) else value for key, value in meta.items()
    }


def readme_heading(text: str) -> tuple[str, str]:
    """A plain README's title and summary: its first heading, and the first paragraph of prose after it."""
    lines = text.split("\n")
    start = next((index for index, line in enumerate(lines) if line.startswith("# ")), None)
    if start is None:
        return "", ""
    paragraph: list[str] = []
    for line in lines[start + 1 :]:
        # Lists, tables, quotes, code, comments and headings are not the summary's prose.
        if not line.strip() or line.startswith(("#", "<!--", "```", "|", "- ", "* ", ">")):
            if paragraph:
                break
            continue
        paragraph.append(line.strip())
    return lines[start][2:].strip(), " ".join(paragraph)


def discover(root: Path, layout: Layout, report: Report) -> Found:
    documents: list[Document] = []
    decisions: list[Document] = []
    readmes: list[PartReadme] = []
    decision = decision_pattern(layout)
    for path in markdown_files(root):
        match = decision.match(path)
        if match:
            meta = read_frontmatter(root, path, report)
            decisions.append(cast(Document, {"path": path, "number": match.group(1), **meta}))
        elif is_document(path, layout):
            documents.append(cast(Document, {"path": path, **read_frontmatter(root, path, report)}))
        elif layout.part_readmes and PurePosixPath(path).name == "README.md" and path != "README.md":
            title, summary = readme_heading((root / path).read_text(encoding="utf-8"))
            if not title:
                report.error(f"{path}: a README next to a part starts with a '# ' heading")
            readmes.append(PartReadme(path, title, summary))
    return Found(documents, decisions, readmes)
