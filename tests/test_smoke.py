"""Phase 0 smoke tests."""

from pulse import __version__


def test_package_version():
    assert __version__ == "0.1.0"
