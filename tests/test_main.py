"""Tests for basic application setup."""

import pytest

import gamatrix_gog


# Testing for argument handling. What happens when we send in valid/invalid
# data into the app?
def test_args_received(monkeypatch, capsys):
    """Ensure arguments are handled correctly."""

    # Set up a fake 'build_config' that gets values from the real one and
    # interrogates them to ensure things are correct
    def build_config_proxy(args):
        pass

    # Replace the build_config used inside the app so we can inspect the values
    # it gets as input, and if the outputs make sense.
    monkeypatch.setattr(gamatrix_gog, "build_config", build_config_proxy)

    # Now call __main__ with arguments and see what happens
    gamatrix_gog.__main__()
