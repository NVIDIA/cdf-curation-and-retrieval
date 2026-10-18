# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the experimental Dataset Search compose asset."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "deploy/compose/docker-compose.yml"
COMPOSE_EMBED = Path(__file__).resolve().parents[2] / "deploy/compose/docker-compose.embed.yml"
MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _compose() -> dict:
    return _load(COMPOSE)


class TestDatasetSearchCompose:
    def test_compose_references_pulled_image_only(self) -> None:
        service = _compose()["services"]["dataset-search"]

        assert service["image"].startswith("${DATASET_SEARCH_IMAGE")
        assert "DATASET_SEARCH_TAG" in service["image"]
        assert "build" not in service

    def test_compose_has_ga_pipeline_init_env(self) -> None:
        service = _compose()["services"]["dataset-search"]

        assert service["environment"]["MILVUS_DB"] == "${MILVUS_DB:-default}"
        assert "host.docker.internal:host-gateway" in service["extra_hosts"]

    def test_ga_compose_keeps_nim_embed_uri(self) -> None:
        env = _compose()["services"]["dataset-search"]["environment"]

        assert "COSMOS_EMBED_NIM_URI" in env
        assert "COSMOS_EMBED_URI" not in env


class TestPublicEmbedOverlay:
    """CDS 1.2.0 needs COSMOS_EMBED_URI and runs Cosmos-Embed1 as a container.

    Without this overlay the public profile starts a healthy API whose pipeline
    never initialises, so the first collection call returns HTTP 500.
    """

    def test_overlay_runs_embed_as_a_pulled_service(self) -> None:
        embed = _load(COMPOSE_EMBED)["services"]["cosmos-embed"]

        assert embed["image"].startswith("${COSMOS_EMBED_IMAGE")
        assert "build" not in embed
        assert embed["ports"] == ["${COSMOS_EMBED_PORT:-9000}:8000"]
        devices = embed["deploy"]["resources"]["reservations"]["devices"]
        assert devices[0]["capabilities"] == ["gpu"]

    def test_overlay_mounts_weights_read_only(self) -> None:
        embed = _load(COMPOSE_EMBED)["services"]["cosmos-embed"]
        mount = embed["volumes"][0]

        assert mount.startswith("${COSMOS_EMBED_MODELS_DIR:?")
        assert mount.endswith(":/models/cosmos-embed1:ro")
        assert embed["environment"]["COSMOS_EMBED_MODEL_PATH"] == "/models/cosmos-embed1"

    def test_overlay_supplies_the_renamed_embed_uri(self) -> None:
        cds = _load(COMPOSE_EMBED)["services"]["dataset-search"]

        assert (
            cds["environment"]["COSMOS_EMBED_URI"]
            == "${COSMOS_EMBED_URI:-http://cosmos-embed:8000}"
        )
        assert cds["depends_on"]["cosmos-embed"]["condition"] == "service_healthy"


class TestPublicProfileWiring:
    """The public profile must reach compose with the embed overlay attached."""

    def _up_recipe(self) -> str:
        text = MAKEFILE.read_text(encoding="utf-8")
        start = text.index("up-dataset-search: check-dataset-search-image")
        return text[start : text.index("\ndown-dataset-search:", start)]

    def test_up_includes_the_embed_overlay_for_public(self) -> None:
        recipe = self._up_recipe()

        assert '[ "$(CDS_PROFILE)" = "public" ]' in recipe
        assert "DATASET_SEARCH_COMPOSE_EMBED" in recipe

    def test_up_refuses_public_without_weights(self) -> None:
        """The CE1 OSS image cannot fetch weights, so a missing dir must fail early."""
        recipe = self._up_recipe()
        guard = recipe[recipe.index('[ "$(CDS_PROFILE)" = "public" ]') :]

        assert "COSMOS_EMBED_MODELS_DIR" in guard
        assert "exit 1" in guard

    def test_down_removes_the_embed_overlay_too(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        down = text[text.index("\ndown-dataset-search:") :][:800]

        assert "DATASET_SEARCH_COMPOSE_EMBED" in down

    def test_embed_overlay_path_is_defined(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")

        assert "DATASET_SEARCH_COMPOSE_EMBED ?= deploy/compose/docker-compose.embed.yml" in text


class TestNoWebUi:
    """The CDS web UI image is not redistributable, so no overlay may ship it."""

    UI_TOKENS = ("cds-ui", "cosmos-cds-ui", "DATASET_SEARCH_UI_", "CDS_UI_")

    def test_no_overlay_defines_a_ui_service(self) -> None:
        for path in (COMPOSE, COMPOSE_EMBED):
            assert "cds-ui" not in _load(path)["services"], f"{path.name} defines a UI service"

    def test_no_overlay_references_ui_variables(self) -> None:
        for path in (COMPOSE, COMPOSE_EMBED):
            text = path.read_text(encoding="utf-8")
            for token in self.UI_TOKENS:
                assert token not in text, f"{path.name} still references {token}"


class TestOnlyPublicOverlaysShip:
    """Only the base stack and the public embed overlay are shipped and wired."""

    REMOVED = ("docker-compose.ea.yml", "docker-compose.prerelease.yml")

    def test_compose_dir_ships_only_base_and_embed(self) -> None:
        shipped = sorted(path.name for path in COMPOSE.parent.glob("docker-compose*.yml"))

        assert shipped == ["docker-compose.embed.yml", "docker-compose.yml"]

    def test_makefile_references_no_removed_overlay(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")

        for name in self.REMOVED:
            assert name not in text, f"Makefile still references {name}"
        assert "DATASET_SEARCH_COMPOSE_EA" not in text
        assert "DATASET_SEARCH_COMPOSE_PRERELEASE" not in text
        assert "ifeq ($(CDS_PROFILE),prerelease)" not in text

    @pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
    def test_internal_profile_starts_only_the_base_stack(self) -> None:
        result = subprocess.run(
            ["make", "-n", "up-dataset-search", "CDS_PROFILE=internal"],
            cwd=MAKEFILE.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        up_line = next(
            (line for line in result.stdout.splitlines() if "compose_files=" in line), ""
        )

        assert up_line, f"no compose invocation in dry run:\n{result.stdout}{result.stderr}"
        assert "docker-compose.ea.yml" not in result.stdout


class TestInternalPullKeepsExtras:
    """The internal profile still pulls the side images its pins name."""

    EXTRAS = (
        "CDS_POSTGRES_IMAGE",
        "COSMOS_EMBED_IMAGE",
        "CAPTION_EMBED_NIM_IMAGE",
        "CRADIO_NIM_IMAGE",
    )

    @pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
    def test_internal_profile_still_pulls_its_extras(self) -> None:
        env = dict(os.environ)
        for name in self.EXTRAS:
            env[name] = f"registry.example/{name.lower()}:pin"
        result = subprocess.run(
            [
                "make",
                "-n",
                "pull-dataset-search",
                "CDS_PROFILE=internal",
                "DATASET_SEARCH_REGISTRY=registry.example/cds",
                "DATASET_SEARCH_TAG=testtag",
            ],
            cwd=MAKEFILE.parent,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        extras_line = next(
            (line for line in result.stdout.splitlines() if "for extra in" in line), ""
        )

        assert extras_line, "internal pull recipe has no extras loop"
        assert extras_line.strip() != 'for extra in "" "" "" ""; do \\', (
            "internal profile must keep pulling its side images"
        )


class TestPublicProfileIsNgcOnly:
    """The public profile is the OSS path and must never reach a private registry.

    `.env` and `local.env` are included before the image defaults, so `?=` would
    let an EA pin silently retarget public. These pins are therefore
    assigned, not defaulted.
    """

    NGC_PINS = {
        "DATASET_SEARCH_REGISTRY": "nvcr.io/nvidia/blueprint/cosmos-dataset-search",
        "DATASET_SEARCH_TAG": "1.2.0",
        "COSMOS_EMBED_IMAGE": "nvcr.io/nvidia/blueprint/cosmos-embed1-oss:1.2.0",
    }
    EA_EXTRAS = ("CDS_POSTGRES_IMAGE", "CAPTION_EMBED_NIM_IMAGE", "CRADIO_NIM_IMAGE")

    def _public_block(self) -> str:
        text = MAKEFILE.read_text(encoding="utf-8")
        start = text.index("ifeq ($(CDS_PROFILE),public)")
        return text[start : text.index("\nelse\n", start)]

    def test_public_block_assigns_ngc_pins_unconditionally(self) -> None:
        block = self._public_block()
        for name, value in self.NGC_PINS.items():
            assert re.search(rf"^{name}\s*=\s*{re.escape(value)}$", block, re.MULTILINE), (
                f"{name} is not unconditionally pinned to {value} on the public profile"
            )
            assert not re.search(rf"^{name}\s*\?=", block, re.MULTILINE), (
                f"{name} uses ?= on the public profile, so .env / local.env wins"
            )

    def test_public_block_empties_entitled_extras(self) -> None:
        block = self._public_block()
        for name in self.EA_EXTRAS:
            assert re.search(rf"^{name}\s*=\s*$", block, re.MULTILINE), (
                f"{name} is not emptied on the public profile"
            )

    def _resolved(self, profile: str, var: str) -> str:
        """Resolve a variable with EA pins exported, as a stale local.env would."""
        env = dict(os.environ)
        env["DATASET_SEARCH_REGISTRY"] = "ghcr.io/example/private-ea/cosmos-dataset-search"
        env["DATASET_SEARCH_TAG"] = "entitled-0.0.0"
        env["COSMOS_EMBED_IMAGE"] = "ghcr.io/example/private-ea/cosmos-embed1:ea"
        for name in self.EA_EXTRAS:
            env[name] = f"ghcr.io/example/private-ea/{name.lower()}:ea"
        root = Path(__file__).resolve().parents[2]
        makefile = f"show-var:\n\t@echo $({var})\n"
        # Run against a copy in an empty directory. The Makefile -includes
        # .env and local.env before the profile defaults, so running in the
        # repository root would resolve the developer's own pins instead of
        # the environment under test.
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(root / "Makefile", Path(tmp) / "Makefile")
            result = subprocess.run(
                ["make", "-f", "Makefile", "-f", "-", "show-var", f"CDS_PROFILE={profile}"],
                cwd=tmp,
                env=env,
                input=makefile,
                capture_output=True,
                text=True,
                check=False,
            )
        return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""

    @pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
    def test_entitled_pins_cannot_retarget_public(self) -> None:
        for name, value in self.NGC_PINS.items():
            assert self._resolved("public", name) == value, (
                f"{name} on the public profile was retargeted by an entitled pin"
            )

    @pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
    def test_entitled_extras_cannot_reach_a_public_pull(self) -> None:
        for name in self.EA_EXTRAS:
            assert self._resolved("public", name) == "", (
                f"{name} leaked into the public profile from the environment"
            )

    @pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
    def test_internal_profile_can_still_be_repinned(self) -> None:
        """Forcing public must not take EA pinning away from the internal profile."""
        resolved = self._resolved("internal", "DATASET_SEARCH_TAG")

        assert resolved == "entitled-0.0.0", f"internal profile lost its pin: {resolved!r}"

    def _image_check_recipe(self) -> str:
        text = MAKEFILE.read_text(encoding="utf-8")
        start = text.index("check-dataset-search-image:")
        return text[start : text.index("\nup-dataset-search:", start)]

    def test_image_check_asserts_ngc_provenance(self) -> None:
        """Pinning the registry variable cannot catch a poisoned local tag.

        Every profile retags into the same neutral name, so a build from another
        registry pulled as the GA tag would satisfy a plain existence check. RepoDigests
        still names the registry the image was pulled from.
        """
        recipe = self._image_check_recipe()

        assert "{{join .RepoDigests" in recipe
        assert "$(DATASET_SEARCH_REGISTRY)@sha256:" in recipe

    def test_provenance_check_is_scoped_to_public(self) -> None:
        """The internal profile legitimately runs images from other registries."""
        recipe = self._image_check_recipe()
        split = recipe.index("{{join .RepoDigests")

        assert '[ "$(CDS_PROFILE)" = "public" ]' in recipe[:split]
        assert "exit 1" in recipe[split:]
