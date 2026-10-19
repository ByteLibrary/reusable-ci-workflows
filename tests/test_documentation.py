"""The documentation generator, run on throwaway repositories in both layouts."""

import contextlib
import io
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from documentation import cli


def frontmatter(title: str, order: int, summary: str = "What it covers") -> str:
    meta = f"title: {title}\nsummary: {summary}\norder: {order}\nstatus: active\nrelated: []"
    return f"---\n{meta}\n---\n\n# {title}\n"


def decision(number: str, status: str = "accepted") -> str:
    meta = f'title: "ADR-{number}: Decide something"\nstatus: {status}\ndate: 2026-10-19\nrelated: []'
    return f"---\n{meta}\n---\n\n# ADR\n"


class Repository:
    """A throwaway git repository with the given files."""

    def __init__(self, files: dict[str, str]) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        for path, text in files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(textwrap.dedent(text))
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)

    def run(self, action: str) -> tuple[int, str]:
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = cli.main([action, "--root", str(self.root)])
        return code, output.getvalue() + errors.getvalue()

    def read(self, path: str) -> str:
        return (self.root / path).read_text()

    def write(self, path: str, text: str) -> None:
        (self.root / path).write_text(text)


README = """\
# example

What this repository is for.

<!-- BEGIN GENERATED index:docs -->
<!-- END GENERATED -->

<!-- BEGIN GENERATED adr-index -->
<!-- END GENERATED -->

<!-- BEGIN GENERATED parts -->
<!-- END GENERATED -->
"""


def repository_layout(**overrides: str) -> dict[str, str]:
    files = {
        "README.md": README,
        "docs/guide.md": frontmatter("Guide", 1),
        "docs/design.md": frontmatter("Design", 2),
        "docs/adr/0001-first.md": decision("0001"),
        "src/part/README.md": "# The part\n\nWhat the part does.\n\n## Modules\n",
    }
    files.update(overrides)
    return files


class RepositoryLayoutTest(unittest.TestCase):
    def repository(self, **overrides: str) -> Repository:
        repository = Repository(repository_layout(**overrides))
        self.addCleanup(repository.directory.cleanup)
        return repository

    def test_generates_the_views_and_llms_txt(self) -> None:
        repository = self.repository()
        code, output = repository.run("generate")
        self.assertEqual(code, 0, output)
        readme = repository.read("README.md")
        self.assertIn("| [Guide](docs/guide.md) | What it covers |", readme)
        self.assertLess(readme.index("Guide"), readme.index("Design"))
        self.assertIn("| [0001](docs/adr/0001-first.md) | Decide something | accepted |", readme)
        self.assertIn("| [The part](src/part/README.md) | What the part does. |", readme)
        llms = repository.read("llms.txt")
        self.assertIn("> What this repository is for.", llms)
        self.assertIn("## Decisions\n- [ADR-0001: Decide something](docs/adr/0001-first.md): accepted", llms)
        self.assertIn("## Parts\n- [The part](src/part/README.md): What the part does.", llms)
        self.assertEqual(repository.run("check")[0], 0)

    def test_a_view_edited_by_hand_fails_the_check(self) -> None:
        repository = self.repository()
        repository.run("generate")
        repository.write("README.md", repository.read("README.md").replace("Guide", "Guides"))
        code, output = repository.run("check")
        self.assertEqual(code, 1)
        self.assertIn("README.md: generated view is out of date", output)

    def test_a_document_without_frontmatter_fails(self) -> None:
        code, output = self.repository(**{"docs/notes.md": "# Notes\n"}).run("check")
        self.assertEqual(code, 1)
        self.assertIn("docs/notes.md: missing frontmatter", output)

    def test_frontmatter_outside_the_schema_fails(self) -> None:
        code, output = self.repository(
            **{"docs/guide.md": frontmatter("Guide", 1).replace("active", "done")}
        ).run("check")
        self.assertEqual(code, 1)
        self.assertIn("'done' is not one of", output)

    def test_two_documents_with_the_same_order_fail(self) -> None:
        code, output = self.repository(**{"docs/design.md": frontmatter("Design", 1)}).run("check")
        self.assertIn("order 1 is also used by", output)

    def test_a_gap_in_decision_numbers_fails(self) -> None:
        code, output = self.repository(**{"docs/adr/0003-third.md": decision("0003")}).run("check")
        self.assertIn("ADR numbers must run from 0001 without gaps", output)

    def test_a_decision_title_must_match_its_number(self) -> None:
        code, output = self.repository(**{"docs/adr/0001-first.md": decision("0002")}).run("check")
        self.assertIn("title must start with 'ADR-0001: '", output)

    def test_a_part_readme_needs_a_heading(self) -> None:
        code, output = self.repository(**{"src/part/README.md": "No heading.\n"}).run("check")
        self.assertIn("src/part/README.md: a README next to a part starts with a '# ' heading", output)

    def test_markers_inside_code_blocks_are_left_alone(self) -> None:
        example = "```markdown\n<!-- BEGIN GENERATED index:docs -->\n<!-- END GENERATED -->\n```\n"
        repository = self.repository(**{"docs/guide.md": frontmatter("Guide", 1) + example})
        repository.run("generate")
        self.assertIn(example, repository.read("docs/guide.md"))

    def test_an_unknown_view_fails(self) -> None:
        code, output = self.repository(
            **{"README.md": "# x\n\n<!-- BEGIN GENERATED nothing -->\n<!-- END GENERATED -->\n"}
        ).run("check")
        self.assertIn("unknown view 'nothing'", output)


class ConfigurationTest(unittest.TestCase):
    def test_docs_toml_moves_the_documents_and_decisions(self) -> None:
        files = {
            "README.md": "# x\n\nWhy.\n",
            "docs.toml": 'documents = "manual"\ndecisions = "manual/decisions"\n',
            "manual/guide.md": frontmatter("Guide", 1),
            "manual/decisions/0001-first.md": decision("0001"),
        }
        repository = Repository(files)
        self.addCleanup(repository.directory.cleanup)
        repository.run("generate")
        self.assertIn(
            "[ADR-0001: Decide something](manual/decisions/0001-first.md)", repository.read("llms.txt")
        )

    def test_an_unknown_setting_fails(self) -> None:
        repository = Repository({"README.md": "# x\n", "docs.toml": "documentz = 'docs'\n"})
        self.addCleanup(repository.directory.cleanup)
        code, output = repository.run("check")
        self.assertIn("docs.toml: unknown setting 'documentz'", output)

    def test_the_sections_layout_needs_a_readme_in_every_section(self) -> None:
        files = {
            "README.md": "# Handbook\n\nWhy.\n",
            "docs.toml": 'sections = true\ndecisions = "90-decisions"\n',
            "00-overview/README.md": frontmatter("Overview", 0),
            "00-overview/vision.md": frontmatter("Vision", 1),
            "10-ways/how.md": frontmatter("How", 1),
        }
        repository = Repository(files)
        self.addCleanup(repository.directory.cleanup)
        code, output = repository.run("check")
        self.assertIn("10-ways/: every section needs a README.md", output)

    def test_an_extension_adds_views_and_checks(self) -> None:
        extension = textwrap.dedent("""\
            def load(root, error):
                return {"colour": "blue"}

            def validate(context, error):
                if context["colour"] != "blue":
                    error("wrong colour")

            def view_colour(colour, **_):
                return f"The colour is {colour}.\\n"

            VIEWS = {"colour": (view_colour, "the extension")}
            """)
        files = {
            "README.md": "# x\n\n<!-- BEGIN GENERATED colour -->\n<!-- END GENERATED -->\n",
            "docs.toml": 'extension = "tools/views.py"\n',
            "tools/views.py": extension,
        }
        repository = Repository(files)
        self.addCleanup(repository.directory.cleanup)
        code, output = repository.run("generate")
        self.assertEqual(code, 0, output)
        self.assertIn("The colour is blue.", repository.read("README.md"))


if __name__ == "__main__":
    unittest.main()
