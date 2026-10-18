# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Docs ↔ Makefile cross-reference guard.

Only one assertion lives here: every ``make <target>`` the skill pack tells an
operator to run must actually exist in the Makefile. A stale skill reference
sends operators to a deleted target, which is a real support bug — not a
documentation style issue — so this check belongs in the test suite rather
than in a lint hook.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"


def _skill_roots() -> list[Path]:
    """Discover every skill pack under ``skills/`` that has a ``SKILL.md``.

    Dynamic discovery keeps this test tolerant of a repo rename (e.g.
    PAIDF→CDF) and of adding further skill packs over time. The caller is
    expected to assert non-emptiness to guard against a vacuous pass if the
    whole directory ever disappears.
    """
    return sorted(p.parent for p in (REPO_ROOT / "skills").glob("*/SKILL.md"))


# Only count a Make call the skill actually presents as a command: start of a
# line, or inside inline code. Prose like "fields make the dataset useful"
# must not be read as a target invocation.
_MAKE_CALL = re.compile(r"(?:^[ \t]*|`)make ([a-z0-9][a-z0-9_-]*)", re.MULTILINE)


def _declared_make_targets() -> set[str]:
    """Collect every target declared in the Makefile's .PHONY blocks.

    Follows backslash continuations the way GNU Make does so multi-line
    .PHONY lists are fully captured.
    """
    targets: set[str] = set()
    collecting = False
    for raw in MAKEFILE.read_text(encoding="utf-8").splitlines():
        line = raw
        if line.startswith(".PHONY:"):
            collecting = True
            line = line[len(".PHONY:") :]
        elif not collecting:
            continue
        line = line.rstrip()
        continues = line.endswith("\\")
        targets.update(line.rstrip("\\").split())
        collecting = continues
    return targets


def test_skill_pack_only_references_declared_make_targets() -> None:
    """Any ``make <target>`` any skill pack prints must exist in the Makefile."""
    declared = _declared_make_targets()
    assert "ds-health" in declared, "parser failed: Makefile .PHONY block not read"

    skill_roots = _skill_roots()
    assert skill_roots, "no skills/<pack>/SKILL.md discovered — skills tree missing?"

    markdown_files = sorted(path for root in skill_roots for path in root.rglob("*.md"))
    assert markdown_files, f"no skill markdown files found under {skill_roots}"

    offenders: set[str] = set()
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for target in _MAKE_CALL.findall(text):
            if target not in declared:
                offenders.add(f"{path.relative_to(REPO_ROOT)}: make {target}")

    assert not offenders, "skill pack references undeclared Make targets:\n" + "\n".join(
        sorted(offenders)
    )
