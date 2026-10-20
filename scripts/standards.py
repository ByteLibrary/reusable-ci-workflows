#!/usr/bin/env python3
"""The ways-of-working rules of the handbook that a machine can check. The Compliance check and the git
hooks on developer machines both call this script, through scripts/standards.sh (ADR-0024).

Usage:
  standards.sh title <title>          a pull request title or a commit subject
  standards.sh commit-message <file>  a commit message, as git passes it to the commit-msg hook
  standards.sh branch <name>          a branch name
  standards.sh description            a pull request description, read from standard input
  standards.sh attribution <what>     text read from standard input, described as <what>
  standards.sh names <what>           text read from standard input, described as <what>

Prints what is wrong and exits with 1 when a rule is broken, and with 2 on wrong usage. Uses only the
standard library, so it runs on the system's Python, before any tool is installed.
"""

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

    def report(self, message: str, details: list[str] = ()) -> None:
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

    def matching(self, pattern: re.Pattern, what: str, text: str, problem: str) -> None:
        lines = [
            f"{number}:{line}" for number, line in enumerate(text.split("\n"), 1) if pattern.search(line)
        ]
        if lines:
            self.report(f"{what} {problem}:", lines[:5])

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


def usage() -> int:
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    rules = Rules()
    command, arguments = (argv[0], argv[1:]) if argv else ("", [])
    if command in ("-h", "--help"):
        print(__doc__)
        return 0
    if command in ("title", "commit-message", "branch") and len(arguments) == 1:
        {"title": rules.title, "commit-message": rules.commit_message, "branch": rules.branch}[command](
            arguments[0]
        )
    elif command == "description" and not arguments:
        rules.description(sys.stdin.read())
    elif command in ("attribution", "names") and len(arguments) == 1:
        getattr(rules, command)(arguments[0], sys.stdin.read())
    else:
        return usage()
    return 1 if rules.broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
