#!/usr/bin/env python3
"""Lints a repository: that it pins each language it uses in its own mise.toml, every language it uses,
with the organization's settings and the tool versions pinned in this repository's mise.toml (Python for
the version its project pins), its documentation if it has a docs/ folder, a docs.toml or an llms.txt,
and then the repository's own `mise run lint`, if it has one. The Lint check in CI and developers run
this same script.

Files marked linguist-generated or linguist-vendored in .gitattributes are skipped. Prints what is wrong,
and exits with 1 when a linter finds a problem.

Example:
  ~/ByteLibrary/reusable-ci-workflows/scripts/lint.py ~/ByteLibrary/playbook
"""

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

RULES = Path(__file__).resolve().parent.parent
# A pinned Python version, such as "3.14.8": its major and minor numbers.
PYTHON_VERSION = re.compile(r"^(\d+)\.(\d+)")
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


def tools(folder: Path) -> dict[str, Any]:
    """The tools pinned in a folder's mise.toml; none when it has no mise.toml."""
    mise_toml = folder / "mise.toml"
    return (
        tomllib.loads(mise_toml.read_text(encoding="utf-8")).get("tools", {}) if mise_toml.is_file() else {}
    )


def python_target(pin: str | list[str]) -> str | None:
    """The ruff target for a pinned Python version, such as py314 for "3.14.8"; None when the pin is not a
    version."""
    match = PYTHON_VERSION.match(str(pin[0] if isinstance(pin, list) else pin))
    return f"py{match.group(1)}{match.group(2)}" if match else None


def python_targets(repository: Path, files: list[str]) -> dict[str | None, list[str]]:
    """The Python files by the ruff target of the version that the nearest mise.toml pinning Python pins,
    from each file's folder up to the repository's root. Files without a pin are under None."""
    by_folder: dict[Path, str | None] = {}

    def target(folder: Path) -> str | None:
        if folder not in by_folder:
            pin = tools(folder).get("python")
            if pin:
                by_folder[folder] = python_target(pin)
            else:
                by_folder[folder] = None if folder == repository else target(folder.parent)
        return by_folder[folder]

    grouped: dict[str | None, list[str]] = {}
    for file in files:
        grouped.setdefault(target(Path(file).parent), []).append(file)
    return grouped


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


def run_quietly(command: list[str], directory: Path) -> subprocess.CompletedProcess[str]:
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

    if (repository / "go.mod").exists() and "go" not in tools(repository):
        print('error: go is used but not pinned: add go = "<version>" under [tools] in mise.toml')
        passed = False

    if scripts := by_language.get("shell"):
        print(f"Shell: {len(scripts)} script(s)")
        for script in scripts:
            passed &= run(["bash", "-n", script], repository)
        passed &= run(pinned("shellcheck", "--severity=warning", "--external-sources", *scripts), RULES)

    if python := by_language.get("python"):
        print(f"Python: {len(python)} file(s)")
        settings = str(RULES / "ruff.toml")
        targets = python_targets(repository, python)
        if unpinned := targets.pop(None, []):
            print(
                'error: python is used but not pinned: add python = "<version>" under [tools] in a mise.toml '
                "in the folder of these files or above:"
            )
            print("\n".join(f"  {Path(file).relative_to(repository)}" for file in unpinned))
            passed = False
        for target, files in sorted((target, files) for target, files in targets.items() if target):
            options = ["--config", settings, "--target-version", target]
            passed &= run(pinned("ruff", "format", "--check", *options, *files), RULES)
            passed &= run(pinned("ruff", "check", *options, *files), RULES)

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
    description, epilog = __doc__.split("\n\n", 1)
    parser = argparse.ArgumentParser(
        prog="lint.py",
        description=description.replace("\n", " "),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repository", nargs="?", default=".", help="the repository's folder (default: the current folder)"
    )
    arguments = parser.parse_args(argv)
    return 0 if lint(Path(arguments.repository).resolve()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
