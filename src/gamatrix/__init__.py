"""
Code to extract the current version from the project's metadata "pyproject.toml" file.

Taken pretty much verbatim from @vengroff's excellent answer to "How to get version from
pyproject.toml from python app?" from GitHub here:
    https://github.com/python-poetry/poetry/issues/273#issuecomment-1877789967
"""

from typing import Any
import importlib.metadata
from pathlib import Path

__package_version = "unknown"


def __get_package_version() -> str:
    """Find the version of this package."""
    global __package_version

    if __package_version != "unknown":
        # We already set it at some point in the past,
        # so return that previous value without any
        # extra work.
        return __package_version

    try:
        # Try to get the version of the current package if
        # it is running from a distribution.
        __package_version = importlib.metadata.version("gamatrix")
    except importlib.metadata.PackageNotFoundError:
        # Fall back on getting it from a local pyproject.toml.
        # This works in a development environment where the
        # package has not been installed from a distribution.
        import tomllib

        pyproject_toml_file = Path(__file__).parent.parent / "pyproject.toml" # parent of /src/gamatrix/__init__.py
        if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
            __package_version = tomllib.load(pyproject_toml_file)["project"]["version"]
            # Indicate it might be locally modified or unreleased.
            __package_version = __package_version + "-localdev"

    return __package_version


def __getattr__(name: str) -> Any:
    """Get package attributes."""
    if name in ("version", "__version__"):
        return __get_package_version()
    else:
        raise AttributeError(f"No attribute {name} in module {__name__}.")
