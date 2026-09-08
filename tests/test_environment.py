"""Environment smoke tests.

These assert the guarantees this project's tooling setup establishes: the
interpreter version, and that the repository root is importable without any
package being installed (see pyproject.toml [tool.pytest.ini_options]
pythonpath, and design.md decision D2). Unlike a throwaway placeholder, this
test remains meaningful for the life of the project and should not be deleted
when apps/ is created.
"""

import sys
from pathlib import Path


def test_python_version() -> None:
    """The running interpreter must satisfy the project's requires-python."""
    assert sys.version_info >= (3, 13), (
        f"expected Python >= 3.13, got {sys.version_info.major}.{sys.version_info.minor}"
    )


def test_repository_root_is_importable() -> None:
    """The repository root must be on sys.path so `apps.*` imports resolve.

    Nothing in this project is installed as a distribution (pyproject.toml
    sets [tool.uv] package = false), so pytest's `pythonpath = ["."]` setting
    is what makes `from apps.papers... import ...` work from HS-004 onward.
    """
    repo_root = Path(__file__).resolve().parent.parent
    assert str(repo_root) in sys.path, (
        f"expected repository root {repo_root} on sys.path; "
        "check pythonpath in [tool.pytest.ini_options]"
    )
