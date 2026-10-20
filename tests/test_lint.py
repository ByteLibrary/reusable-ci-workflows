"""The lint script: which files it lints as what, and, on throwaway repositories with the pinned tools,
each language with a case that must pass and one that must fail, a language used without a pin, skipped
files, documentation and a repository's own lint task."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"
RULES = SCRIPT.parent.parent

spec = importlib.util.spec_from_file_location("lint", SCRIPT)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)

CLEAN_SHELL = '#!/usr/bin/env bash\necho "hello"\n'
# A variable that is never used is a shellcheck warning (SC2034).
BROKEN_SHELL = '#!/usr/bin/env bash\nunused="value"\n'
FRONTMATTER = (
    "---\ntitle: Guide\nsummary: How to use it\norder: 1\nstatus: active\nrelated: []\n---\n\n# Guide\n"
)


class FilesTest(unittest.TestCase):
    def test_generated_and_vendored_files_are_skipped(self) -> None:
        output = (
            "gen/a.sh\0linguist-generated\0set\0gen/a.sh\0linguist-vendored\0unspecified\0"
            "b.sh\0linguist-generated\0unspecified\0b.sh\0linguist-vendored\0unspecified\0"
            "v/c.sh\0linguist-generated\0unspecified\0v/c.sh\0linguist-vendored\0true\0"
        )
        self.assertEqual(lint.skipped(output), {"gen/a.sh", "v/c.sh"})

    def test_languages_used_without_a_pin(self) -> None:
        self.assertEqual(lint.unpinned({"python", "go", "shell"}, ""), ["go", "python"])
        self.assertEqual(lint.unpinned({"python"}, '[tools]\nuv = "0.12.23"\n'), ["python"])
        self.assertEqual(lint.unpinned({"python", "shell"}, '[tools]\npython = "3.14.8"\n'), [])

    def test_languages_by_extension_or_shebang(self) -> None:
        self.assertEqual(lint.language("scripts/run.sh", ""), "shell")
        self.assertEqual(lint.language("app.py", ""), "python")
        self.assertEqual(lint.language("hooks/pre-push", "#!/usr/bin/env bash\n"), "shell")
        self.assertEqual(lint.language("bin/tool", "#!/bin/sh\n"), "shell")
        self.assertIsNone(lint.language("hooks/notes", "unused=value\n"))
        self.assertIsNone(lint.language("README.md", "#!/usr/bin/env bash\n"))


class LintTest(unittest.TestCase):
    """The whole script, with the tools pinned in this repository's mise.toml."""

    def repository(self, files: dict[str, str], trust: bool = False) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
        for path, text in files.items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text)
        subprocess.run(["git", "add", "--all"], cwd=root, check=True)
        if trust:
            subprocess.run(["mise", "trust", "--quiet", str(root / "mise.toml")], check=True)
        return root

    def assertLint(self, expected: bool, root: Path) -> None:
        result = subprocess.run([str(SCRIPT), str(root)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, expected, result.stdout + result.stderr)

    def test_no_code(self) -> None:
        self.assertLint(True, self.repository({"README.md": "# Empty\n"}))

    def test_shell(self) -> None:
        self.assertLint(True, self.repository({"run.sh": CLEAN_SHELL}))
        self.assertLint(False, self.repository({"run.sh": BROKEN_SHELL}))
        self.assertLint(False, self.repository({"hooks/pre-push": BROKEN_SHELL}))
        self.assertLint(True, self.repository({"hooks/notes": "unused=value\n"}))

    def test_generated_and_vendored_files(self) -> None:
        self.assertLint(
            True,
            self.repository({"gen/run.sh": BROKEN_SHELL, ".gitattributes": "gen/** linguist-generated\n"}),
        )
        self.assertLint(
            True,
            self.repository(
                {"vendor/run.sh": BROKEN_SHELL, ".gitattributes": "vendor/** linguist-vendored\n"}
            ),
        )

    def python_repository(self, code: str, pinned: bool = True) -> Path:
        files = {"app.py": code, "mise.toml": '[tools]\npython = "3.14.8"\n' if pinned else "[tools]\n"}
        return self.repository(files, trust=True)

    def test_python(self) -> None:
        self.assertLint(True, self.python_repository('print("hello")\n'))
        self.assertLint(False, self.python_repository("print( 'hello' )\n"))
        self.assertLint(False, self.python_repository('import os\n\nprint("hello")\n'))
        self.assertLint(False, self.python_repository('print("hello")\n', pinned=False))

    def go_repository(self, code: str, pinned: bool = True) -> Path:
        files = {
            "go.mod": "module example.com/check\n\ngo 1.27.1\n",
            "mise.toml": '[tools]\ngo = "1.27.1"\n' if pinned else "[tools]\n",
            "main.go": code,
        }
        return self.repository(files, trust=True)

    def test_go(self) -> None:
        self.assertLint(
            True,
            self.go_repository('package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("hello")\n}\n'),
        )
        # An error that is never checked is a lint error (errcheck, one of the standard linters).
        self.assertLint(
            False, self.go_repository('package main\n\nimport "os"\n\nfunc main() {\n\tos.Remove("x")\n}\n')
        )
        self.assertLint(
            False,
            self.go_repository('package main\n\nimport "fmt"\n\nfunc main() {\nfmt.Println( "hello" )\n}\n'),
        )
        self.assertLint(
            False,
            self.go_repository(
                'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("hello")\n}\n', pinned=False
            ),
        )

    def test_documentation(self) -> None:
        good = self.repository({"README.md": "# Example\n\nWhat it is for.\n", "docs/guide.md": FRONTMATTER})
        generate = [
            "uv",
            "run",
            "--quiet",
            "--frozen",
            "documentation",
            "generate",
            "--quiet",
            "--root",
            str(good),
        ]
        subprocess.run(["mise", "exec", "--", *generate], cwd=RULES, check=True)
        self.assertLint(True, good)
        self.assertLint(
            False,
            self.repository({"README.md": "# Example\n\nWhat it is for.\n", "docs/guide.md": "# Guide\n"}),
        )

    def test_own_lint_task(self) -> None:
        self.assertLint(True, self.repository({"mise.toml": '[tasks.lint]\nrun = "true"\n'}, trust=True))
        self.assertLint(False, self.repository({"mise.toml": '[tasks.lint]\nrun = "false"\n'}, trust=True))


if __name__ == "__main__":
    unittest.main()
