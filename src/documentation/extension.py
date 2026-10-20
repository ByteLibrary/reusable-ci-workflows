"""A repository's own views and checks, loaded from the Python file docs.toml names.

The file may define:
  VIEWS                 extra views, as {name: (function, what it is generated from)}
  load(root, error)     extra data the views and checks use, as a dict added to every view's arguments
  validate(context, error)  extra checks; `error(message)` reports a problem
"""

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from documentation.layout import Layout
from documentation.report import Report
from documentation.views import Views

# The function an extension calls to report a problem.
Error = Callable[[str], None]
# The arguments every view is called with, by name.
Context = dict[str, object]


def no_data(root: Path, error: Error) -> Context:
    return {}


def no_checks(context: Context, error: Error) -> None:
    return None


@dataclass(frozen=True, slots=True)
class Extension:
    views: Views = field(default_factory=dict)
    load: Callable[[Path, Error], Context] = no_data
    validate: Callable[[Context, Error], None] = no_checks


def load_extension(root: Path, layout: Layout, report: Report) -> Extension:
    if not layout.extension:
        return Extension()
    path = root / layout.extension
    spec = importlib.util.spec_from_file_location("documentation_extension", path)
    if not path.exists() or spec is None or spec.loader is None:
        report.error(f"docs.toml: extension {layout.extension} does not exist")
        return Extension()
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return Extension(
        views=getattr(module, "VIEWS", {}),
        load=getattr(module, "load", no_data),
        validate=getattr(module, "validate", no_checks),
    )
