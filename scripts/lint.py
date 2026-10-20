#!/usr/bin/env python3
"""Lints a repository: that it pins each language it uses in its own mise.toml, every language it uses,
with the organization's settings and the tool versions pinned in this repository's mise.toml, its
documentation if it has a docs/ folder, a docs.toml or an llms.txt, and then the repository's own
`mise run lint`, if it has one. The Lint check in CI and developers run this same script.

Usage: lint.py [<repository>]   the repository's folder, by default the current one

Files marked linguist-generated or linguist-vendored in .gitattributes are skipped. Prints what is wrong,
and exits with 1 when a linter finds a problem.

Example:
  ~/ByteLibrary/reusable-ci-workflows/scripts/lint.py ~/ByteLibrary/playbook
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

RULES = Path(__file__).resolve().parent.parent
# The mise tool that pins each language a repository may use. Shell runs on the machine's own bash.
PINS = {"python": "python", "go": "go"}
# A shebang that runs a shell script: bash or sh, by path or through env.
SHELL_SHEBANG = re.compile(r"^#!.*\b(ba)?sh\b")


def skipped(check_attr_output: str) -> set[str]:
    """Files marked generated or vendored, from `git check-attr -z` output: path, attribute, value, each
    ending with a NUL."""
    fields = check_attr_output.split("\0")
    return {fields[index] for index in range(0, len(fields) - 2, 3) if fields[index + 2] in ("set", "true")}


def language(path: str, first_line: str) -> str | None:
    """The language a tracked file is linted as: by its extension, or for a file without one, by its
    shebang (as git hooks have none)."""
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".sh"):
        return "shell"
    if name.endswith(".py"):
        return "python"
    if "." not in name and SHELL_SHEBANG.match(first_line):
        return "shell"
    return None


def unpinned(languages: set[str], mise_toml: str) -> list[str]:
    """The languages used without a pin in the repository's mise.toml (its text, empty when it has none)."""
    tools = tomllib.loads(mise_toml).get("tools", {})
    return sorted(PINS[name] for name in languages if name in PINS and PINS[name] not in tools)


def tracked_files(repository: Path) -> list[str]:
    listed = run_quietly(["git", "ls-files", "-z"], repository).stdout
    files = [path for path in listed.split("\0") if path]
    attributes = subprocess.run(
        ["git", "check-attr", "--stdin", "-z", "linguist-generated", "linguist-vendored"],
        cwd=repository,
        input="\0".join(files),
        capture_output=True,
        text=True,
    ).stdout
    leave_out = skipped(attributes)
    return sorted(path for path in files if path not in leave_out and (repository / path).is_file())


def first_line(path: Path) -> str:
    with path.open(encoding="utf-8", errors="ignore") as file:
        return file.readline()


def run_quietly(command: list[str], directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=directory, capture_output=True, text=True)


def run(command: list[str], directory: Path) -> bool:
    """Runs a linter, showing its output; True when it found nothing."""
    return subprocess.run(command, cwd=directory).returncode == 0


def pinned(*command: str) -> list[str]:
    """A tool at the version pinned in this repository's mise.toml (run from this repository)."""
    return ["mise", "exec", "--", *command]


def lint(repository: Path) -> bool:
    files = tracked_files(repository)
    by_language: dict[str, list[str]] = {}
    for path in files:
        found = language(path, first_line(repository / path))
        if found:
            by_language.setdefault(found, []).append(str(repository / path))
    passed = True

    used = set(by_language) | ({"go"} if (repository / "go.mod").exists() else set())
    mise_toml = repository / "mise.toml"
    for tool in unpinned(used, mise_toml.read_text(encoding="utf-8") if mise_toml.exists() else ""):
        print(f'error: {tool} is used but not pinned: add {tool} = "<version>" under [tools] in mise.toml')
        passed = False

    if scripts := by_language.get("shell"):
        print(f"Shell: {len(scripts)} script(s)")
        for script in scripts:
            passed &= run(["bash", "-n", script], repository)
        passed &= run(pinned("shellcheck", "--severity=warning", "--external-sources", *scripts), RULES)

    if python := by_language.get("python"):
        print(f"Python: {len(python)} file(s)")
        settings = str(RULES / "ruff.toml")
        passed &= run(pinned("ruff", "format", "--check", "--config", settings, *python), RULES)
        passed &= run(pinned("ruff", "check", "--config", settings, *python), RULES)

    if (repository / "go.mod").exists():
        print("Go")
        # golangci-lint is pinned here, but analyzes the code with the Go version the repository pins, so
        # it runs in the repository, with the repository's tools.
        golangci_lint = run_quietly(["mise", "which", "golangci-lint"], RULES).stdout.strip()
        settings = str(RULES / ".golangci.yml")
        passed &= run(["mise", "exec", "--", golangci_lint, "run", "--config", settings, "./..."], repository)

    if any((repository / name).exists() for name in ("docs", "docs.toml", "llms.txt")):
        print("Documentation")
        check = [
            "uv",
            "run",
            "--quiet",
            "--frozen",
            "documentation",
            "check",
            "--quiet",
            "--root",
            str(repository),
        ]
        passed &= run(pinned(*check), RULES)

    if (repository / "mise.toml").exists() and run_quietly(
        ["mise", "tasks", "info", "lint"], repository
    ).returncode == 0:
        print("This repository's own lint task")
        passed &= run(["mise", "run", "lint"], repository)

    return passed


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(argv) > 1:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    return 0 if lint(Path(argv[0] if argv else ".").resolve()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
