"""The generated views every repository can use, and the helpers a repository's own views build on.

A view is a function called with keyword arguments: `source` (the file it is written into), `folder`
(the argument after its name in the marker, if any), `root`, `documents`, `decisions`, `readmes`, and
whatever the repository's extension loads. It returns Markdown.
"""

import os
import pathlib
from collections.abc import Callable, Sequence

from documentation.documents import Document, PartReadme
from documentation.rules import sections

View = Callable[..., str]
# Views by the name their marker uses, each with what it is generated from.
Views = dict[str, tuple[View, str]]


def table(header: list[str], rows: Sequence[tuple[str, ...]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell for cell in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def relative(source: str, target: str) -> str:
    """A link from one file to another, both relative to the root."""
    return os.path.relpath(target, os.path.dirname(source) or ".")


def by_path(documents: list[Document]) -> dict[str, Document]:
    return {document["path"]: document for document in documents}


def index_entries(documents: list[Document], folder: str) -> list[Document]:
    """Documents directly in a folder, plus the READMEs of its direct subfolders, in reading order."""
    entries: list[Document] = []
    for document in documents:
        path = pathlib.PurePosixPath(document["path"])
        direct = str(path.parent) == folder and path.name != "README.md"
        subfolder_readme = path.name == "README.md" and str(path.parent.parent) == folder
        if direct or subfolder_readme:
            entries.append(document)
    return sorted(
        entries,
        key=lambda document: (
            document["path"].count("/") - folder.count("/"),
            document["order"],
            document["path"],
        ),
    )


def view_index(source: str, folder: str, documents: list[Document], **_: object) -> str:
    rows = [
        (f"[{document['title']}]({relative(source, document['path'])})", document["summary"])
        for document in index_entries(documents, folder)
    ]
    return table(["Document", "Covers"], rows)


def view_sections(source: str, root: pathlib.Path, documents: list[Document], **_: object) -> str:
    readmes = by_path(documents)
    rows = [
        (
            f"[{section}]({relative(source, section + '/README.md')})",
            readmes[f"{section}/README.md"]["summary"],
        )
        for section in sections(root)
        if f"{section}/README.md" in readmes
    ]
    return table(["Section", "Contents"], rows)


def view_adr_index(source: str, decisions: list[Document], **_: object) -> str:
    rows = [
        (
            f"[{decision['number']}]({relative(source, decision['path'])})",
            decision["title"].split(": ", 1)[1],
            decision["status"],
        )
        for decision in sorted(decisions, key=lambda decision: decision["number"])
    ]
    return table(["ADR", "Decision", "Status"], rows)


def view_parts(source: str, readmes: list[PartReadme], **_: object) -> str:
    rows = [
        (f"[{readme.title}]({relative(source, readme.path)})", readme.summary)
        for readme in sorted(readmes, key=lambda readme: readme.path)
    ]
    return table(["Part", "Covers"], rows)


VIEWS: Views = {
    "index": (view_index, "the frontmatter of the listed documents"),
    "sections": (view_sections, "the frontmatter of each section's README.md"),
    "adr-index": (view_adr_index, "the frontmatter of each ADR"),
    "parts": (view_parts, "the first heading and paragraph of each part's README.md"),
}
