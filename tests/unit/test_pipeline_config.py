# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for Cosmos Curator configuration preflight validation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from apps.cli.__main__ import main
from apps.cli.pipeline_config import validate_curator_pipeline_config
from apps.workflows import RunCuratorPipelineRequest, run_curator_pipeline


@pytest.mark.parametrize(
    ("placement", "deprecated_key", "canonical_key"),
    [
        ("top_level", "enable_sam3", "sam3"),
        ("top_level", "enable_event_captioning", "event_captioning"),
        ("args", "enable_sam3", "sam3"),
        ("args", "enable_event_captioning", "event_captioning"),
    ],
)
def test_rejects_deprecated_keys_in_supported_placements(
    tmp_path: Path,
    placement: str,
    deprecated_key: str,
    canonical_key: str,
) -> None:
    config = tmp_path / "split.yaml"
    key_line = f"{deprecated_key}: true\n"
    contents = f"pipeline: split\n{key_line}"
    if placement == "args":
        contents = f"pipeline: split\nargs:\n  {key_line}"
    config.write_text(contents, encoding="utf-8")

    with pytest.raises(click.ClickException) as error:
        validate_curator_pipeline_config(config)

    assert deprecated_key in error.value.message
    assert canonical_key in error.value.message


@pytest.mark.parametrize(
    "contents",
    [
        "pipeline: split\nsam3: true\nevent_captioning: true\n",
        "pipeline: split\nargs:\n  sam3: true\n  event_captioning: true\n",
    ],
)
def test_accepts_canonical_keys_in_supported_placements(
    tmp_path: Path,
    contents: str,
) -> None:
    config = tmp_path / "split.yaml"
    config.write_text(contents, encoding="utf-8")

    validate_curator_pipeline_config(config)


@pytest.mark.parametrize("args_value", ["null", "false", "split", "[]"])
def test_non_mapping_args_follow_curator_top_level_fallback(
    tmp_path: Path,
    args_value: str,
) -> None:
    config = tmp_path / "split.yaml"
    config.write_text(
        f"pipeline: split\nargs: {args_value}\nsam3: true\nevent_captioning: true\n",
        encoding="utf-8",
    )

    validate_curator_pipeline_config(config)


def test_does_not_scan_metadata_overrides(tmp_path: Path) -> None:
    config = tmp_path / "metadata.yaml"
    config.write_text(
        "cosmos_curator:\n  overrides:\n    enable_sam3: true\n    enable_event_captioning: true\n",
        encoding="utf-8",
    )

    validate_curator_pipeline_config(config)


@pytest.mark.parametrize("contents", ["pipeline: [unterminated", "- split\n- sam3"])
def test_rejects_malformed_configuration(tmp_path: Path, contents: str) -> None:
    config = tmp_path / "split.yaml"
    config.write_text(contents, encoding="utf-8")

    with pytest.raises(click.ClickException):
        validate_curator_pipeline_config(config)


def test_reports_unreadable_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "split.yaml"
    config.write_text("pipeline: split\n", encoding="utf-8")
    monkeypatch.setattr(Path, "read_text", MagicMock(side_effect=PermissionError))

    with pytest.raises(click.ClickException, match="could not be read"):
        validate_curator_pipeline_config(config)


def test_cli_validates_before_runner_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "split.yaml"
    config.write_text(
        "pipeline: split\nargs:\n  enable_sam3: true\n",
        encoding="utf-8",
    )
    runner_factory = MagicMock()
    monkeypatch.setattr("apps.cli.__main__.build_curator_runner", runner_factory)

    result = CliRunner().invoke(main, ["curator-run", "--config-file", str(config)])

    assert result.exit_code == 1
    assert "enable_sam3" in result.output
    assert "sam3" in result.output
    runner_factory.assert_not_called()


def test_cli_preserves_canonical_config_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "split.yaml"
    config.write_text(
        "pipeline: split\nsam3: true\nevent_captioning: true\n",
        encoding="utf-8",
    )
    runner = MagicMock()
    runner.run_pipeline.return_value = SimpleNamespace(command=["docker", "run"])
    monkeypatch.setattr("apps.cli.__main__.build_curator_runner", lambda **_: runner)

    result = CliRunner().invoke(
        main,
        ["curator-run", "--config-file", str(config), "--dry-run"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"dry_run": True, "command": ["docker", "run"]}
    runner.run_pipeline.assert_called_once()


def test_cli_help_remains_click_text() -> None:
    result = CliRunner().invoke(main, ["curator-run", "--help"])

    assert result.exit_code == 0
    assert result.output.startswith("Usage:")


def test_workflow_validates_before_runner_construction() -> None:
    runner_factory = MagicMock()

    def reject_config(config_file: str | Path) -> None:
        raise click.ClickException(f"invalid config: {config_file}")

    with pytest.raises(click.ClickException, match="invalid config"):
        run_curator_pipeline(
            RunCuratorPipelineRequest(config_file="bad.yaml"),
            runner_factory=runner_factory,
            validate_config=reject_config,
        )

    runner_factory.assert_not_called()


def test_workflow_passes_request_to_runner() -> None:
    runner = MagicMock()
    runner.run_pipeline.return_value = SimpleNamespace(command=("docker", "run"))
    validate_config = MagicMock()

    result = run_curator_pipeline(
        RunCuratorPipelineRequest(
            config_file="split.yaml",
            data_dir="data",
            models_dir="models",
            ffmpeg_dir="ffmpeg",
            dry_run=True,
        ),
        runner_factory=lambda: runner,
        validate_config=validate_config,
    )

    validate_config.assert_called_once_with("split.yaml")
    runner.run_pipeline.assert_called_once_with(
        "split.yaml",
        data_dir="data",
        models_dir="models",
        ffmpeg_dir="ffmpeg",
        dry_run=True,
    )
    assert result.dry_run is True
    assert result.command == ["docker", "run"]
