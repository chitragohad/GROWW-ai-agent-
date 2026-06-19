"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Repository root for tests."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def groww_config_path(project_root: Path) -> Path:
    return project_root / "config" / "products" / "groww.yaml"


@pytest.fixture
def pipeline_config_path(project_root: Path) -> Path:
    return project_root / "config" / "pipeline.yaml"
