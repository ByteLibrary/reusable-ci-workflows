"""Rendering: the generated views inside documents, the notices of their statuses, and llms.txt."""

import pathlib
import re
from collections.abc import Mapping

from documentation.documents import Document, Found
from documentation.extension import Context
from documentation.layout import Layout
from documentation.report import Report
from documentation.rules import sections
from documentation.views import Views, summary

# A marker that starts a generated view: its name, an optional argument, then any text.
BEGIN = re.compile(r"^<!-- BEGIN GENERATED (?P<view>[a-z-]+)(?::(?P<arg>\S+))?(?: [^\n]*)? ?-->$")
END = "<!-- END GENERATED -->"
# The view a status's notice is written with, under a document's first heading.
NOTICE = "notice"


def outside_code(lines: list[str]) -> list[int]:
    """The indexes of the lines that are not inside fenced code blocks, nor in the frontmatter."""
    indexes, in_fence = [], False
    start = lines.index("---", 1) + 1 if lines and lines[0] == "---" and "---" in lines[1:] else 0
    for index in range(start, len(lines)):
        if lines[index].startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            indexes.append(index)
    return indexes


def is_notice(line: str) -> bool:
    marker = BEGIN.match(line)
    return marker is not None and marker.group("view") == NOTICE


def place_notice(path: str, text: str, notice: str | None, report: Report) -> str:
    """The text with its status's notice under its first heading, or without one if the status has none."""
    lines = text.split("\n")
    begin = next((index for index in outside_code(lines) if is_notice(lines[index])), None)
    if begin is not None and END in lines[begin:]:
        end = lines.index(END, begin)
        del lines[begin - 1 if begin and not lines[begin - 1] else begin : end + 1]
    if notice is None:
        return "\n".join(lines)
    heading = next((index for index in outside_code(lines) if lines[index].startswith("# ")), None)
    if heading is None:
        report.error(f"{path}: its status shows a notice, which goes under a '# ' heading it does not have")
        return text
    lines[heading + 1 : heading + 1] = ["", f"<!-- BEGIN GENERATED {NOTICE} -->", END]
    return "\n".join(lines)


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


def render_llms(root: pathlib.Path, layout: Layout, found: Found, notices: Mapping[str, str]) -> str:
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
                f"- [{document['title']}]({document['path']}): {summary(document, notices)}"
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
                    f"- [{document['title']}]({document['path']}): {summary(document, notices)}"
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
    root: pathlib.Path,
    layout: Layout,
    found: Found,
    views: Views,
    context: Context,
    notices: Mapping[str, str],
    report: Report,
) -> dict[str, str]:
    """Every generated file, as its new text: the files with markers or a notice, and llms.txt."""
    files: dict[str, str] = {}
    documented = {item["path"] for item in found.documents + found.decisions}
    paths = [
        "README.md",
        *(item["path"] for item in found.documents + found.decisions),
        *(readme.path for readme in found.readmes),
    ]
    for path in paths:
        if not (root / path).exists():
            continue
        text = (root / path).read_text(encoding="utf-8")
        if path in documented:
            text = place_notice(path, text, notices.get(path), report)
        if "BEGIN GENERATED" in text or text != (root / path).read_text(encoding="utf-8"):
            files[path] = render_markers(path, text, views, context, report)
    if (root / "README.md").exists():
        files["llms.txt"] = render_llms(root, layout, found, notices)
    return files
