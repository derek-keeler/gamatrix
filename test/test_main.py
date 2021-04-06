"""Test for functions present in gamatrix_gog's __main__ module."""

import pathlib
from typing import Any

# import pytest

from gamatrix_gog import __main__ as gog


def always_false(self: Any):
    return False


def always_true(self: Any):
    return True


def test_is_sqlite3(monkeypatch):

    monkeypatch.setattr(pathlib.Path, "exists", always_false)
    assert gog.isSQLite3("test_path") == False


def test_is_sqlite3_2(monkeypatch):

    monkeypatch.setattr(pathlib.Path, "exists", always_true)
    monkeypatch.setattr(pathlib.Path, "is_file", always_false)
    assert gog.isSQLite3("test_path") == False

    # """Fast check to ensure a file is indeed an SQLite3 db file, based on the format."""
    # # Thanks! https://stackoverflow.com/a/15355790/895739

    # test_sql_file = pathlib.Path(path)

    # if not test_sql_file.exists():
    #     return False
    # if not test_sql_file.is_file():
    #     return False

    # with open(test_sql_file.absolute().as_uri(), "rb") as file_:
    #     header = file_.read(100)

    #     if len(header) != 100:
    #         return False

    #     return header[:16] == b"SQLite format 3\000"


def test_allowed_files():
    pass


# def allowed_file(filename):
#     """Returns True if filename has an allowed extension"""
#     return (
#         "." in filename
#         and filename.rsplit(".", 1)[1].lower() in constants.UPLOAD_ALLOWED_EXTENSIONS
#     )