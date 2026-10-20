"""The rules script, as the git hooks and the Compliance check run it: every rule with a case that must
pass and one that must fail."""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "standards.py"

spec = importlib.util.spec_from_file_location("standards", SCRIPT)
assert spec is not None and spec.loader is not None
standards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standards)
# A banned name, read from the script, so the list stays in one place.
BANNED = standards.NAMES.pattern.split("(")[1].split("|")[0]

COMPLETE = "Closes #3\n\n## Why\nBecause.\n\n## What changed\nThis.\n\n## How it was verified\nTests."


def run(*arguments: str, stdin: str = "") -> int:
    environment = {key: value for key, value in os.environ.items() if key != "GITHUB_ACTIONS"}
    return subprocess.run(
        [str(SCRIPT), *arguments], input=stdin, capture_output=True, text=True, env=environment
    ).returncode


class RulesTest(unittest.TestCase):
    def message(self, *lines: str) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "message"
        path.write_text("\n".join(lines) + "\n")
        return str(path)

    def test_titles(self) -> None:
        self.assertEqual(run("title", "feat(catalog): add work relations"), 0)
        self.assertEqual(run("title", "feat!: drop the old api"), 0)
        for title in ("feature: add work relations", "feat: Add work relations", "feat: add work relations."):
            with self.subTest(title=title):
                self.assertEqual(run("title", title), 1)

    def test_commit_messages(self) -> None:
        passing = [
            ("fix: ignore stale positions", "", "Positions older than the stored one are dropped."),
            ("docs: fix a typo", "# Please enter the commit message"),
            (
                "docs: fix a typo",
                "# ------------------------ >8 ------------------------",
                "Co-authored-by: someone",
            ),
            ("fixup! docs: fix a typo",),
        ]
        failing = [
            ("Fix typo",),
            ("docs: fix a typo", "", "Co-authored-by: someone <someone@example.com>"),
            ("docs: fix a typo", "", "Generated with some tool"),
            (f"docs: thank {BANNED}",),
        ]
        for lines in passing:
            with self.subTest(passing=lines):
                self.assertEqual(run("commit-message", self.message(*lines)), 0)
        for lines in failing:
            with self.subTest(failing=lines):
                self.assertEqual(run("commit-message", self.message(*lines)), 1)

    def test_branches(self) -> None:
        self.assertEqual(run("branch", "feat/12-work-relations"), 0)
        for branch in (
            "feat/work-relations",
            "feature/12-work-relations",
            "feat/12-Work-Relations",
            f"feat/12-{BANNED}-setup",
        ):
            with self.subTest(branch=branch):
                self.assertEqual(run("branch", branch), 1)

    def test_descriptions(self) -> None:
        self.assertEqual(run("description", stdin=COMPLETE), 0)
        self.assertEqual(
            run("description", stdin=COMPLETE.replace("Closes #3", "Closes ByteLibrary/roadmap#26")), 0
        )
        self.assertEqual(run("description", stdin=COMPLETE.replace("Closes #3", "")), 1)
        self.assertEqual(run("description", stdin=COMPLETE.replace("## Why\n", "")), 1)

    def test_attribution_and_names(self) -> None:
        self.assertEqual(run("attribution", "The text", stdin="plain text"), 0)
        self.assertEqual(run("attribution", "The text", stdin="Co-Authored-By: someone"), 1)
        self.assertEqual(run("names", "The text", stdin="an agent tool"), 0)
        self.assertEqual(run("names", "The text", stdin=f"Thanks {BANNED.upper()}"), 1)

    def test_help(self) -> None:
        self.assertEqual(run("--help"), 0)

    def test_wrong_usage(self) -> None:
        self.assertEqual(run("unknown"), 2)
        self.assertEqual(run("title"), 2)


if __name__ == "__main__":
    unittest.main()
