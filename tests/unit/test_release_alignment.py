# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Release version alignment guard.

``pyproject.toml`` is the single source of the product version. Every other
place a release states its version must agree with it, otherwise a release
ships with a lockfile, README, changelog, or signed skill that names a
different version than the package.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "skills" / "cdf-curation-and-retrieval"
PROJECT_NAME = "cdf-curation-and-retrieval"


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _product_version() -> str:
    match = re.search(r'^version = "([^"]+)"$', _read("pyproject.toml"), re.MULTILINE)
    assert match is not None, "pyproject.toml has no [project] version"
    return match.group(1)


PRODUCT_VERSION = _product_version()
MAJOR_MINOR = ".".join(PRODUCT_VERSION.split(".")[:2])


def test_product_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", PRODUCT_VERSION), PRODUCT_VERSION


def test_uv_lock_project_version_matches_pyproject() -> None:
    match = re.search(
        rf'^name = "{PROJECT_NAME}"\nversion = "([^"]+)"$', _read("uv.lock"), re.MULTILINE
    )
    assert match is not None, f"uv.lock has no {PROJECT_NAME} package entry"
    assert match.group(1) == PRODUCT_VERSION


def test_readme_reports_product_version() -> None:
    text = _read("README.md")
    assert f"**Version:** {PRODUCT_VERSION}" in text
    assert f"uv project (version {PRODUCT_VERSION})" in text


def test_latest_changelog_entry_is_product_version() -> None:
    headings = re.findall(r"^## \[([^\]]+)\]", _read("CHANGELOG.md"), re.MULTILINE)
    assert headings, "CHANGELOG.md has no release headings"
    assert headings[0] == PRODUCT_VERSION


def test_skill_frontmatter_matches_product_version() -> None:
    frontmatter = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
    match = re.search(r"^\s+version: (\S+)$", frontmatter, re.MULTILINE)
    assert match is not None, "SKILL.md frontmatter has no metadata.version"
    assert match.group(1) == PRODUCT_VERSION


def test_skill_card_matches_product_version() -> None:
    text = (SKILL_ROOT / "skill-card.md").read_text(encoding="utf-8")
    assert f"{PRODUCT_VERSION} (source: frontmatter, pyproject.toml)" in text


@pytest.mark.parametrize("relative", ["SKILL.md", "evals/evals.json"])
def test_skill_names_only_the_current_release_line(relative: str) -> None:
    text = (SKILL_ROOT / relative).read_text(encoding="utf-8")
    stale = sorted({v for v in re.findall(r"\bCDF v(\d+\.\d+)\b", text) if v != MAJOR_MINOR})
    assert not stale, f"{relative} names CDF release line(s) {stale}, expected v{MAJOR_MINOR}"
