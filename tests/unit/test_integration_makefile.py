# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Safety checks for the local/operator Make façade."""

from __future__ import annotations

from pathlib import Path

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"


def _recipe(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    start = text.index(f"{target}:")
    next_target = text.find("\n\n", start)
    return text[start : next_target if next_target >= 0 else len(text)]


def test_integration_make_targets_are_noninteractive() -> None:
    for target in (
        "stage-cds-artifact",
        "ds-bulk-insert",
        "ds-job-status",
        "caption-readiness",
        "caption-search",
        "caption-upload",
        "caption-from-curator",
        "caption-bulk-insert",
        "prepare-cds-ce1-for-tdm",
        "run-image-embeddings",
    ):
        assert "read -p" not in _recipe(target)


def test_caption_from_curator_make_target_uses_curator_output_root() -> None:
    recipe = _recipe("caption-from-curator")
    assert "CURATOR_DIR" in recipe
    assert "integration captions from-curator" in recipe
    assert "CAPTION_JSON" not in recipe
    help_text = MAKEFILE.read_text(encoding="utf-8")
    assert "make caption-from-curator" in help_text


def test_makefile_uses_component_scoped_internal_cli() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "CDF_CLI ?= cdf_curation_and_retrieval" in text
    assert "uv run cdf " not in text


def test_object_store_make_targets_pass_credential_names_not_values() -> None:
    recipes = "\n".join(
        [
            _recipe("stage-cds-artifact"),
            _recipe("ds-bulk-insert"),
            _recipe("caption-bulk-insert"),
        ]
    )
    assert "--access-key-env" in recipes
    assert "--secret-key-env" in recipes
    assert "--access-key " not in recipes
    assert "--secret-key " not in recipes


def test_cds_bulk_and_tdm_handoff_require_ce1_declaration() -> None:
    recipes = "\n".join([_recipe("ds-bulk-insert"), _recipe("prepare-cds-ce1-for-tdm")])

    assert recipes.count('--embedding-family "$(CDS_EMBEDDING_FAMILY)"') == 2
    assert recipes.count("ERROR: CDS_EMBEDDING_FAMILY=ce1 required") == 2


def test_cds_make_targets_forward_the_configured_cds_url() -> None:
    """CDS_URL is set in the Makefile and never exported, so recipes must pass it down."""
    cds_targets = (
        "ds-health",
        "ds-collections",
        "ds-get-collection",
        "ds-bulk-insert",
        "ds-job-status",
        "caption-stats",
        "ingest-curator",
    )
    unreachable: list[str] = []
    for target in cds_targets:
        recipe = _recipe(target)
        if '--cds-url "$(CDS_URL)"' not in recipe and 'CDS_URL="$(CDS_URL)"' not in recipe:
            unreachable.append(target)
    assert not unreachable, f"these recipes silently use the default CDS URL: {unreachable}"


def test_ds_get_collection_documents_the_id_only_contract() -> None:
    """CDS resolves this endpoint by id; a name returns 404, so help must not offer one."""
    recipe = _recipe("ds-get-collection")
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "ERROR: COLLECTION= required" in recipe
    assert "collection id" in recipe
    assert "404" in recipe
    assert "name or id" not in recipe
    assert "COLLECTION=<collection-id>" in text


def test_make_owns_public_tao_image_and_passes_it_explicitly() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "DATA_MINING_REGISTRY ?= nvcr.io/nvidia/tao/tao-toolkit" in text
    assert "DATA_MINING_TAG ?= 7.2.0-data-services" in text
    assert "DATA_MINING_IMAGE ?= tao-toolkit" in text
    assert "TDM_EMBEDDING_BACKEND ?= ce1" in text
    for target in (
        "run-data-mining-select",
        "run-data-mining-unique-match",
        "run-image-embeddings",
    ):
        assert '--image "$(DATA_MINING_IMAGE):$(DATA_MINING_TAG)"' in _recipe(target)
        if target != "run-image-embeddings":
            assert '--embedding-backend "$(TDM_EMBEDDING_BACKEND)"' in _recipe(target)


def test_make_documents_tao_ds_experiment_and_metric_contract() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "Every invocation requires an experiment spec" in text
    assert "DATA_MINING_METRIC=cosine|euclidean|manhattan" in text
    assert "distance_threshold" in text
    assert "SOURCE_EMBED_COLUMN_NAME" in text
    assert "run-data-mining-unique-match" in text
    assert "unique_neighbor_matching" in text
    assert "SOURCE_DETECTION_FILE" in text
    assert "RARE_CLASS_LIST" in text
    assert "FILTER_BY_LABEL" in text
    assert "DETECTION_FORMAT=coco (JSON file) | kitti (label dir)" in text
    assert "--source-embed-column-name" in _recipe("run-data-mining-select")
    assert "--filter-by-label" in _recipe("run-data-mining-select")
    assert "--source-detection-file" in _recipe("run-data-mining-unique-match")
    assert "--save-embeddings" in _recipe("run-data-mining-unique-match")


def test_default_model_list_includes_internvideo2_bert_sidecar() -> None:
    """InternVideo2 does not vendor google-bert/bert-large-uncased."""
    text = MAKEFILE.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if row.startswith("MODEL_LIST ?="))
    tokens = [token.strip() for token in line.split("?=", 1)[1].split(",")]
    assert "internvideo2_mm" in tokens
    assert "bert" in tokens


def test_t5_xxl_reduction_uses_the_default_pixi_env() -> None:
    """model-download has no torch, so t5_xxl must not be reduced there."""
    recipe = _recipe("download-models")
    assert "grep -vx 't5_xxl'" in recipe
    assert "download_one model-download" in recipe
    assert "download_one default t5_xxl" in recipe
    assert "pixi run -e $$pixi_env" in recipe


def test_env_example_paths_use_make_syntax_for_home() -> None:
    """Make includes .env and reads ``$HOME`` as ``$H`` + ``OME``."""
    for row in (MAKEFILE.parent / ".env.example").read_text(encoding="utf-8").splitlines():
        if not row.startswith("#") and "=" in row:
            assert "$HOME" not in row, row


def test_ffmpeg_preflight_names_the_install_target() -> None:
    setup = _recipe("check-setup")
    runtime = _recipe("check-curator-runtime")
    for recipe in (setup, runtime):
        assert "make ffmpeg-install FFMPEG_DIR=$(FFMPEG_DIR)" in recipe


def test_make_exposes_text_embedding_subtask() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    recipe = _recipe("run-text-embeddings")

    assert "TEXT_EMBEDDING_MODEL=clip|siglip|siglip2" in text
    assert "integration text-embeddings run" in recipe
    assert '--image "$(DATA_MINING_IMAGE):$(DATA_MINING_TAG)"' in recipe
    assert "read -p" not in recipe
    assert "integration text-embeddings validate-output" in _recipe(
        "text-embeddings-validate-output"
    )
