#!/usr/bin/env python3
"""The ways-of-working rules of the handbook that a machine can check. The Compliance check and the git
hooks on developer machines both call this script (ADR-0024).

Prints what is wrong and exits with 1 when a rule is broken, and with 2 on wrong usage. Uses only the
standard library, so it runs on the system's Python, before any tool is installed.

Examples:
  standards.py title "feat: add the catalog"
  git log --format=%B main..HEAD | standards.py attribution "A commit message"
"""

import argparse
import os
import re
import sys
from pathlib import Path

TYPES = "feat|fix|refactor|perf|test|docs|build|ci|chore"

# Names of AI agents, assistants and vendors that must not appear in ByteLibrary content
# (handbook, ADR-0017). This list is the only place where they are written down.
NAMES = re.compile(r"\b(claude|anthropic|openai|chatgpt|codex|copilot|gemini|windsurf)\b", re.IGNORECASE)

# Co-author trailers, and tool attribution lines such as "Generated with …".
ATTRIBUTION = re.compile(r"^co-authored-by:|^(🤖 )?generated (with|by) ", re.IGNORECASE)

# A Conventional Commit: type, optional scope, optional "!", then a lowercase description without a
# trailing period.
TITLE = re.compile(rf"^({TYPES})(\([a-z0-9-]+\))?!?: [a-z0-9`].*[^.]$")

# <type>/<issue-number>-<short-description>, in lowercase kebab-case.
BRANCH = re.compile(rf"^({TYPES})/[0-9]+-[a-z0-9]+(-[a-z0-9]+)*$")

# The line that closes the pull request's issue, in this repository or another of the organization.
CLOSES = re.compile(r"^closes (ByteLibrary/[A-Za-z0-9._-]+)?#[0-9]+", re.IGNORECASE | re.MULTILINE)

HEADINGS = ("## Why", "## What changed", "## How it was verified")

# git's scissors line in a verbose commit message: everything below it is ignored.
SCISSORS = re.compile(r"^# -{24} >8 -{24}$", re.MULTILINE)


class Rules:
    """Checks text against the rules, and reports every broken one."""

    def __init__(self) -> None:
        self.broken = False

    def report(self, message: str, details: tuple[str, ...] = ()) -> None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::error::{message}")
        else:
            print(f"error: {message}", file=sys.stderr)
        for line in details:
            print(line, file=sys.stderr)
        self.broken = True

    def title(self, title: str) -> None:
        if not TITLE.match(title):
            self.report(
                f"'{title}' is not a Conventional Commit: '<type>(<scope>): <description>', lowercase, "
                "imperative, without a trailing period."
            )

    def matching(self, pattern: re.Pattern[str], what: str, text: str, problem: str) -> None:
        lines = [
            f"{number}:{line}" for number, line in enumerate(text.split("\n"), 1) if pattern.search(line)
        ]
        if lines:
            self.report(f"{what} {problem}:", tuple(lines[:5]))

    def attribution(self, what: str, text: str) -> None:
        self.matching(ATTRIBUTION, what, text, "contains co-author trailers or tool attribution")

    def names(self, what: str, text: str) -> None:
        self.matching(NAMES, what, text, "names a specific agent tool or vendor")

    def commit_message(self, path: str) -> None:
        text = Path(path).read_text(encoding="utf-8")
        scissors = SCISSORS.search(text)
        if scissors:
            text = text[: scissors.start()]
        message = "\n".join(line for line in text.split("\n") if not line.startswith("#"))
        subject = next((line for line in message.split("\n") if line.strip()), "")
        # Fixup commits are squashed away before the branch is merged.
        if not re.match(r"^(fixup|squash|amend)! ", subject):
            self.title(subject)
        self.attribution("The commit message", message)
        self.names("The commit message", message)

    def branch(self, name: str) -> None:
        if not BRANCH.match(name):
            self.report(
                f"'{name}' is not a branch name of the form '<type>/<issue-number>-<short-description>', "
                "in lowercase kebab-case."
            )
        self.names("The branch name", name)

    def description(self, body: str) -> None:
        body = body.replace("\r", "")
        if not CLOSES.search(body):
            self.report("The description is missing a line 'Closes #<issue>'.")
        lines = body.split("\n")
        for heading in HEADINGS:
            if heading not in lines:
                self.report(f"The description is missing the heading '{heading}'.")


def parser() -> argparse.ArgumentParser:
    description, epilog = __doc__.split("\n\n", 1)
    parser = argparse.ArgumentParser(
        prog="standards.py",
        description=description.replace("\n", " "),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rules = parser.add_subparsers(dest="rule", required=True, metavar="<rule>")
    rules.add_parser("title", help="a pull request title or a commit subject").add_argument("title")
    rules.add_parser(
        "commit-message", help="a commit message, as git passes it to the commit-msg hook"
    ).add_argument("file")
    rules.add_parser("branch", help="a branch name").add_argument("name")
    rules.add_parser("description", help="a pull request description, read from standard input")
    for rule in ("attribution", "names"):
        rules.add_parser(rule, help="text read from standard input, described as <what>").add_argument(
            "what", help="what the text is, for the messages, such as 'A commit message'"
        )
    return parser


def main(argv: list[str]) -> int:
    arguments = parser().parse_args(argv)
    rules = Rules()
    match arguments.rule:
        case "title":
            rules.title(arguments.title)
        case "commit-message":
            rules.commit_message(arguments.file)
        case "branch":
            rules.branch(arguments.name)
        case "description":
            rules.description(sys.stdin.read())
        case "attribution":
            rules.attribution(arguments.what, sys.stdin.read())
        case "names":
            rules.names(arguments.what, sys.stdin.read())
    return 1 if rules.broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
