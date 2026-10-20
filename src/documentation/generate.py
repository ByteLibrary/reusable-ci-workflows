"""Rendering: the generated views inside documents, and llms.txt."""

import pathlib
import re

from documentation.documents import Document, Found
from documentation.extension import Context
from documentation.layout import Layout
from documentation.report import Report
from documentation.rules import sections
from documentation.views import Views

# A marker that starts a generated view: its name, an optional argument, then any text.
BEGIN = re.compile(r"^<!-- BEGIN GENERATED (?P<view>[a-z-]+)(?::(?P<arg>\S+))?(?: [^\n]*)? ?-->$")
END = "<!-- END GENERATED -->"


def render_markers(path: str, text: str, views: Views, context: Context, report: Report) -> str:
    """Re-renders every generated view in a file.

    Scanned line by line: a BEGIN marker counts only outside fenced code blocks (markers inside them are
    examples), and everything up to the matching END marker is replaced, code blocks included.
    """
    lines, index, in_fence = text.split("\n"), 0, False
    output: list[str] = []
    while index < len(lines):
        line = lines[index]
        begin = None if in_fence else BEGIN.match(line)
        if line.startswith("```"):
            in_fence = not in_fence
        if not begin:
            output.append(line)
            index += 1
            continue
        end = next((position for position in range(index + 1, len(lines)) if lines[position] == END), None)
        view, arg = begin.group("view"), begin.group("arg")
        if end is None or view not in views:
            problem = "no END GENERATED marker" if end is None else f"unknown view '{view}'"
            report.error(f"{path}: line {index + 1}: {problem}")
            return text
        function, source = views[view]
        name = f"{view}:{arg}" if arg else view
        body = function(source=path, folder=arg, **context)
        output.append(
            f"<!-- BEGIN GENERATED {name} · source: {source} · edit the source, then run `mise run docs` -->"
        )
        output += body.rstrip("\n").split("\n")
        output.append(END)
        index = end + 1
    return "\n".join(output)


def reading_order(document: Document) -> tuple[int, str, int, str]:
    path = pathlib.PurePosixPath(document["path"])
    return (document["path"].count("/"), str(path.parent), document.get("order", 0), document["path"])


def render_llms(root: pathlib.Path, layout: Layout, found: Found) -> str:
    """llms.txt: the README's title and first paragraph, then every document, decision and part."""
    readme = (root / "README.md").read_text(encoding="utf-8").split("\n\n")
    lines = [readme[0].strip(), ""]
    if len(readme) > 1:
        lines += ["> " + readme[1].strip().replace("\n", "\n> "), ""]
    decisions = [
        f"- [{decision['title']}]({decision['path']}): {decision['status']}"
        for decision in sorted(found.decisions, key=lambda decision: decision["number"])
    ]
    if layout.sections:
        titles = {document["path"]: document["title"] for document in found.documents}
        for section in sections(root):
            lines.append(f"## {titles[section + '/README.md']}")
            in_section = [
                document for document in found.documents if document["path"].startswith(section + "/")
            ]
            lines += [
                f"- [{document['title']}]({document['path']}): {document['summary']}"
                for document in sorted(in_section, key=reading_order)
            ]
            if layout.decisions.split("/")[0] == section:
                lines += decisions
            lines.append("")
    else:
        groups = [
            (
                "Documentation",
                [
                    f"- [{document['title']}]({document['path']}): {document['summary']}"
                    for document in sorted(found.documents, key=reading_order)
                ],
            ),
            ("Decisions", decisions),
            (
                "Parts",
                [
                    f"- [{readme.title}]({readme.path}): {readme.summary}"
                    for readme in sorted(found.readmes, key=lambda readme: readme.path)
                ],
            ),
        ]
        for heading, entries in groups:
            if entries:
                lines += [f"## {heading}", *entries, ""]
    lines.append(
        "<!-- Generated from the frontmatter of every document. "
        "Edit the documents, then run `mise run docs`. -->"
    )
    return "\n".join(lines) + "\n"


def generated_files(
    root: pathlib.Path, layout: Layout, found: Found, views: Views, context: Context, report: Report
) -> dict[str, str]:
    """Every generated file, as its new text: the files with markers, and llms.txt."""
    files: dict[str, str] = {}
    paths = [
        "README.md",
        *(item["path"] for item in found.documents + found.decisions),
        *(readme.path for readme in found.readmes),
    ]
    for path in paths:
        if not (root / path).exists():
            continue
        text = (root / path).read_text(encoding="utf-8")
        if "BEGIN GENERATED" in text:
            files[path] = render_markers(path, text, views, context, report)
    if (root / "README.md").exists():
        files["llms.txt"] = render_llms(root, layout, found)
    return files
